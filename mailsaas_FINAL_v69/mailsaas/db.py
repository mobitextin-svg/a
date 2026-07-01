"""
SQLite data layer for the MailSaaS enterprise platform.

A thin, dependency-free wrapper around sqlite3 that gives us:
  * a per-request connection stored on Flask's `g`
  * Row access by column name
  * automatic schema creation / seeding on first run

Everything is multi-tenant aware: almost every table carries an
``account_id`` so a single deployment can serve many isolated tenants.
"""
import os
import sqlite3
import json
from datetime import datetime

from flask import g, current_app

# --------------------------------------------------------------------------- #
#  Connection handling
# --------------------------------------------------------------------------- #


def get_db():
    """Return the sqlite connection for the current request (lazy)."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        # Wait briefly instead of erroring when the background sender holds a
        # write lock (live progress polls read concurrently).
        g.db.execute("PRAGMA busy_timeout = 8000")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    lastrow = cur.lastrowid
    cur.close()
    return lastrow


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
#  Schema
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'Free',
    credits      INTEGER NOT NULL DEFAULT 1000,
    region       TEXT NOT NULL DEFAULT 'us-east',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    email        TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    pw_hash      TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'Owner',
    timezone     TEXT NOT NULL DEFAULT 'UTC',
    twofa        INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    last_login   TEXT
);

CREATE TABLE IF NOT EXISTS verifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    email        TEXT NOT NULL,
    result       TEXT NOT NULL,            -- valid / invalid / risky / unknown
    score        INTEGER NOT NULL DEFAULT 0,
    reason       TEXT,
    detail       TEXT,                     -- JSON of sub-checks
    source       TEXT NOT NULL DEFAULT 'single',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_lists (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    list_id      INTEGER,
    email        TEXT NOT NULL,
    name         TEXT,
    tags         TEXT,
    status       TEXT NOT NULL DEFAULT 'active',  -- active/blocked/unsubscribed/bounced
    created_at   TEXT NOT NULL
);

-- Manually-blocked addresses for the Suppression List → "Blocked Emails".
-- Unsubscribed / bounced / complaint suppressions are derived from contact
-- status and the complaints table; this table holds explicit user blocks.
CREATE TABLE IF NOT EXISTS blocked_emails (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    email        TEXT NOT NULL,
    reason       TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blocked_acct ON blocked_emails(account_id, email);

-- User-defined custom contact fields (Contact Settings → Custom Fields).
CREATE TABLE IF NOT EXISTS contact_fields (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    label        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    subject      TEXT,
    preview_text TEXT,
    body         TEXT,
    from_email   TEXT,
    status       TEXT NOT NULL DEFAULT 'Draft',   -- Draft/Scheduled/Running/Completed/Failed
    recipients   INTEGER NOT NULL DEFAULT 0,
    sent         INTEGER NOT NULL DEFAULT 0,
    opens        INTEGER NOT NULL DEFAULT 0,
    clicks       INTEGER NOT NULL DEFAULT 0,
    bounces      INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS smtp_servers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    host         TEXT NOT NULL,
    port         INTEGER NOT NULL DEFAULT 587,
    username     TEXT,
    dedicated_ip TEXT,
    daily_limit  INTEGER NOT NULL DEFAULT 10000,
    sent_today   INTEGER NOT NULL DEFAULT 0,
    warmup       TEXT NOT NULL DEFAULT 'Not started',
    health       TEXT NOT NULL DEFAULT 'Healthy',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS domains (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    domain       TEXT NOT NULL,
    spf          INTEGER NOT NULL DEFAULT 0,
    dkim         INTEGER NOT NULL DEFAULT 0,
    dmarc        INTEGER NOT NULL DEFAULT 0,
    verified     INTEGER NOT NULL DEFAULT 0,
    reputation   INTEGER NOT NULL DEFAULT 80,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    label        TEXT NOT NULL,
    token        TEXT NOT NULL,
    last_used    TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    actor        TEXT,
    action       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    number       TEXT NOT NULL,
    amount       REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Paid',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'Email',   -- Email / Landing / Block
    subject      TEXT,
    content      TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS template_folders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_templates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL,                   -- Education / Healthcare / ...
    name         TEXT NOT NULL,
    subject      TEXT,
    content      TEXT,
    published    INTEGER NOT NULL DEFAULT 1,      -- visible to all users when 1
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    trigger      TEXT NOT NULL,
    steps        INTEGER NOT NULL DEFAULT 1,
    status       TEXT NOT NULL DEFAULT 'Active',   -- Active / Paused / Draft
    enrolled     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS landing_pages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    slug         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Draft',    -- Draft / Published
    views        INTEGER NOT NULL DEFAULT 0,
    submissions  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhooks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    url          TEXT NOT NULL,
    events       TEXT NOT NULL,                    -- comma list of event names
    secret       TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    last_status  TEXT,
    deliveries   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    user_email   TEXT NOT NULL,
    ip           TEXT,
    agent        TEXT,
    ok           INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

-- Indexes for fast tenant-scoped queries on large datasets.
CREATE INDEX IF NOT EXISTS idx_contacts_acct       ON contacts(account_id);
CREATE INDEX IF NOT EXISTS idx_contacts_acct_email ON contacts(account_id, email);
CREATE INDEX IF NOT EXISTS idx_contacts_acct_status ON contacts(account_id, status);
CREATE INDEX IF NOT EXISTS idx_verif_acct          ON verifications(account_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_acct      ON campaigns(account_id);
CREATE INDEX IF NOT EXISTS idx_users_acct          ON users(account_id);
CREATE INDEX IF NOT EXISTS idx_login_acct          ON login_history(account_id);

CREATE TABLE IF NOT EXISTS burst_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    size         INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',   -- running / completed
    ips_used     TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coupons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE NOT NULL,
    percent      INTEGER NOT NULL DEFAULT 10,
    redemptions  INTEGER NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    campaign_id  INTEGER NOT NULL,
    email        TEXT NOT NULL,
    token        TEXT UNIQUE NOT NULL,
    smtp_id      INTEGER,
    status       TEXT NOT NULL DEFAULT 'sent',   -- sent / dry-run / failed
    error        TEXT,
    opened       INTEGER NOT NULL DEFAULT 0,
    clicked      INTEGER NOT NULL DEFAULT 0,
    opened_at    TEXT,
    clicked_at   TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_campaign ON messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_messages_token    ON messages(token);

CREATE TABLE IF NOT EXISTS complaints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    campaign_id  INTEGER,
    email        TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'complaint',  -- complaint / unsubscribe
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_complaints_acct ON complaints(account_id);

CREATE TABLE IF NOT EXISTS integrations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    provider     TEXT UNIQUE NOT NULL,
    connected    INTEGER NOT NULL DEFAULT 0,
    config       TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER,
    endpoint     TEXT NOT NULL,
    ip           TEXT,
    status       INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_apilogs_acct ON api_logs(account_id);

CREATE TABLE IF NOT EXISTS burst_purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    emails       INTEGER NOT NULL,
    amount       REAL NOT NULL,
    currency     TEXT NOT NULL,
    gateway      TEXT NOT NULL,
    method       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'paid',  -- active / pending / rejected
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_settings (
    key          TEXT PRIMARY KEY,
    value        TEXT
);

-- Campaign file attachments. While the wizard is open, files are staged under
-- a session `token`; on campaign creation they're linked via `campaign_id`.
CREATE TABLE IF NOT EXISTS campaign_attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    campaign_id  INTEGER,
    token        TEXT,
    filename     TEXT NOT NULL,
    stored       TEXT NOT NULL,
    size         INTEGER NOT NULL DEFAULT 0,
    mime         TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attach_campaign ON campaign_attachments(campaign_id);
CREATE INDEX IF NOT EXISTS idx_attach_token    ON campaign_attachments(token);

-- Audit trail of contact imports, powering each list's "Import History" view.
CREATE TABLE IF NOT EXISTS contact_imports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    list_id      INTEGER,
    filename     TEXT,
    rows         INTEGER NOT NULL DEFAULT 0,   -- rows seen in the upload
    added        INTEGER NOT NULL DEFAULT 0,   -- new contacts created
    updated      INTEGER NOT NULL DEFAULT 0,   -- existing contacts updated
    skipped      INTEGER NOT NULL DEFAULT 0,   -- duplicates skipped
    rule         TEXT,                         -- skip / update / keep
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_tags (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    color        TEXT NOT NULL DEFAULT 'blue',
    description  TEXT,
    favorite     INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    created_at   TEXT NOT NULL,
    UNIQUE(account_id, name)
);

-- Per-contact event log: tag added/removed, note added, imported.
-- Sent/opened/clicked/bounced events are derived live from `messages`.
CREATE TABLE IF NOT EXISTS contact_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    contact_id   INTEGER NOT NULL,
    kind         TEXT NOT NULL,      -- imported / tag_added / tag_removed / note
    detail       TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cevents_contact ON contact_events(contact_id);
"""


def get_setting(key, default=None):
    row = query("SELECT value FROM platform_settings WHERE key=?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute("INSERT INTO platform_settings (key, value) VALUES (?,?) ON CONFLICT(key)"
            " DO UPDATE SET value=excluded.value", (key, str(value)))

# Idempotent column additions for accounts that predate these features.
_MIGRATIONS = [
    ("accounts", "gst_number", "TEXT"),
    ("accounts", "auto_renew", "INTEGER NOT NULL DEFAULT 1"),
    ("accounts", "payment_provider", "TEXT NOT NULL DEFAULT 'Stripe'"),
    ("accounts", "coupon", "TEXT"),
    ("accounts", "is_admin", "INTEGER NOT NULL DEFAULT 0"),
    ("accounts", "onboarding", "TEXT NOT NULL DEFAULT ''"),  # completed step keys
    # Authentication hardening.
    ("users", "verified", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "verify_token", "TEXT"),
    ("users", "reset_token", "TEXT"),
    ("users", "reset_expires", "TEXT"),
    ("users", "totp_secret", "TEXT"),
    ("users", "session_token", "TEXT"),
    ("users", "status", "TEXT NOT NULL DEFAULT 'active'"),  # active / suspended
    # Smart-rotation engines.
    ("smtp_servers", "purpose", "TEXT NOT NULL DEFAULT 'normal'"),  # normal / burst
    ("smtp_servers", "busy", "INTEGER NOT NULL DEFAULT 0"),         # reserved & in-use
    ("smtp_servers", "password", "TEXT"),                          # optional, for real send
    ("smtp_servers", "use_tls", "INTEGER NOT NULL DEFAULT 1"),
    ("accounts", "ip_allowlist", "TEXT"),     # comma IPs/CIDRs; empty = allow all
    ("domains", "bimi", "INTEGER NOT NULL DEFAULT 0"),
    ("accounts", "burst_quota", "INTEGER NOT NULL DEFAULT 0"),  # purchased one-time boost
    ("accounts", "burst_valid_until", "TEXT"),                  # when the boost expires
    ("burst_purchases", "valid_until", "TEXT"),
    ("burst_purchases", "duration_days", "INTEGER NOT NULL DEFAULT 1"),
    # Campaigns can target a specific contact list (null = all active contacts).
    ("campaigns", "list_id", "INTEGER"),
    # Bulk-sender controls: emails/minute throttle + how many to send per run.
    ("campaigns", "send_rate", "INTEGER"),
    ("campaigns", "batch_size", "INTEGER"),
    ("burst_purchases", "reason", "TEXT"),
    ("burst_purchases", "used", "INTEGER NOT NULL DEFAULT 0"),  # emails consumed
    # Personal template organisation (folders, favorites, trash, provenance).
    ("templates", "folder", "TEXT NOT NULL DEFAULT 'General'"),
    ("templates", "favorite", "INTEGER NOT NULL DEFAULT 0"),
    ("templates", "trashed", "INTEGER NOT NULL DEFAULT 0"),
    ("templates", "source_id", "INTEGER"),   # system_templates.id this was copied from
    # Quick Email builder — stores the field values (logo/subject/body/cta…) as
    # JSON so re-opening a template returns to the friendly form, not raw HTML.
    ("templates", "fields_json", "TEXT"),
    ("system_templates", "fields_json", "TEXT"),
    # Extra contact fields so personalisation variables resolve to real data.
    ("contacts", "company", "TEXT"),
    ("contacts", "mobile", "TEXT"),
    ("contacts", "city", "TEXT"),
    ("contacts", "state", "TEXT"),
    # Campaign preview text shown after subject in inbox previews.
    ("campaigns", "preview_text", "TEXT"),
    # Contact List Management: each list has a channel type and remembers its
    # most recent import so the management screen can show it at a glance.
    ("contact_lists", "list_type", "TEXT NOT NULL DEFAULT 'Universal'"),  # Email/SMS/WhatsApp/Universal
    ("contact_lists", "last_import_at", "TEXT"),
    # Track which import batch each contact was added by (for smart batch delete).
    ("contacts", "import_id", "INTEGER"),
    # Contact Settings: how duplicates are detected on import and the default
    # rule applied when none is chosen.
    ("accounts", "dup_check", "TEXT NOT NULL DEFAULT 'email'"),       # email / email_name
    ("accounts", "default_import_rule", "TEXT NOT NULL DEFAULT 'remove'"),  # remove / skip / update
    # Internal per-contact notes and the contact's standard optional fields are
    # already present (company/mobile/city/state). Notes are new.
    ("contacts", "note", "TEXT"),
    # Pin frequently-used lists to the top of the rail.
    ("contact_lists", "favorite", "INTEGER NOT NULL DEFAULT 0"),
    # Import audit: store the invalid/blank counts and the failed rows (JSON) so
    # the UI can show a summary and offer an error-report download.
    ("contact_imports", "invalid", "INTEGER NOT NULL DEFAULT 0"),
    ("contact_imports", "blanks", "INTEGER NOT NULL DEFAULT 0"),
    ("contact_imports", "errors_json", "TEXT"),
    # Template-level default preview text (the grey inbox line). Campaigns
    # auto-fill their own preview_text from this when a template is picked,
    # but can still override it per campaign.
    ("templates", "preview_text", "TEXT"),
    ("system_templates", "preview_text", "TEXT"),
    # Tag Colors / Description / Favorite / Last-used (existing account_tags
    # rows from earlier versions won't have these columns yet).
    ("account_tags", "color", "TEXT NOT NULL DEFAULT 'blue'"),
    ("account_tags", "description", "TEXT"),
    ("account_tags", "favorite", "INTEGER NOT NULL DEFAULT 0"),
    ("account_tags", "last_used_at", "TEXT"),
    # Recently-used tags, account-wide, most-recent-first comma list (for the
    # quick-pick chips while editing/tagging a contact).
    ("accounts", "recent_tags", "TEXT NOT NULL DEFAULT ''"),
    # Contact Trash (soft delete). Deleting a contact sets status='trashed' and
    # stamps `deleted_at`; `restore_status` remembers the status to restore it
    # to. Because trashed contacts leave the 'active' status, every existing
    # status='active' send/count query excludes them automatically.
    ("contacts", "deleted_at", "TEXT"),
    ("contacts", "restore_status", "TEXT"),
    # Extra personalization fields so {{country}}/{{balance}}/{{last_purchase}}
    # merge tags resolve to real data (used by the Insert Variable menu).
    ("contacts", "country", "TEXT"),
    ("contacts", "balance", "TEXT"),
    ("contacts", "last_purchase", "TEXT"),
]


def _migrate():
    db = get_db()
    for table, col, decl in _MIGRATIONS:
        cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    db.commit()


def mark_onboarding(account_id, step):
    """Record that a user has completed an onboarding step (idempotent).
    Tracks real actions, separately from the demo data an account is seeded with."""
    row = query("SELECT onboarding FROM accounts WHERE id=?", (account_id,), one=True)
    done = set(filter(None, (row["onboarding"] if row else "").split(",")))
    if step not in done:
        done.add(step)
        execute("UPDATE accounts SET onboarding=? WHERE id=?",
                (",".join(sorted(done)), account_id))


def log_activity(account_id, actor, action):
    execute(
        "INSERT INTO activity (account_id, actor, action, created_at) VALUES (?,?,?,?)",
        (account_id, actor, action, now()),
    )


def log_contact_event(account_id, contact_id, kind, detail=""):
    """Record a per-contact timeline event (imported / tag_added / tag_removed / note)."""
    execute(
        "INSERT INTO contact_events (account_id, contact_id, kind, detail, created_at)"
        " VALUES (?,?,?,?,?)",
        (account_id, contact_id, kind, detail, now()),
    )


def touch_recent_tag(account_id, tag_name):
    """Push a tag to the front of the account's recently-used list (max 10, de-duped)."""
    row = query("SELECT recent_tags FROM accounts WHERE id=?", (account_id,), one=True)
    recent = [t for t in (row["recent_tags"] if row else "").split(",") if t and t != tag_name]
    recent.insert(0, tag_name)
    execute("UPDATE accounts SET recent_tags=? WHERE id=?",
            (",".join(recent[:10]), account_id))
    execute("UPDATE account_tags SET last_used_at=? WHERE account_id=? AND name=?",
            (now(), account_id, tag_name))


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    _migrate()
    # Seed default coupons once.
    if not query("SELECT 1 FROM coupons LIMIT 1", (), one=True):
        for code, pct in [("WELCOME20", 20), ("SAVE50", 50), ("ENTERPRISE", 30)]:
            execute("INSERT INTO coupons (code, percent, active, created_at)"
                    " VALUES (?,?,?,?)", (code, pct, 1, now()))
    # Burst pool defaults to auto-approve on payment.
    if get_setting("burst_auto_approve") is None:
        set_setting("burst_auto_approve", "1")
    # Seed the admin-owned system template library once.
    seed_system_templates()


SYSTEM_TEMPLATE_SEED = [
    ("Education", "Admission Open", "Admissions are now open at {{org}}!",
     "<h1>Admissions Open for 2027</h1><p>Hi {{name}},</p><p>We're excited to "
     "announce that admissions at <b>{{org}}</b> are now open. Limited seats — "
     "apply early.</p><p><a href=\"{{link}}\">Apply Now</a></p>"),
    ("Education", "Fee Reminder", "Reminder: fee payment due on {{date}}",
     "<h1>Fee Payment Reminder</h1><p>Dear {{name}},</p><p>This is a gentle "
     "reminder that the fee for {{org}} is due on <b>{{date}}</b>. Please pay "
     "to avoid a late charge.</p><p><a href=\"{{link}}\">Pay Fees</a></p>"),
    ("Education", "Result Announcement", "{{org}} results are out",
     "<h1>Results Announced</h1><p>Hi {{name}},</p><p>The results for the latest "
     "term are now available. Log in to view your scorecard.</p>"
     "<p><a href=\"{{link}}\">View Result</a></p>"),
    ("Healthcare", "Appointment Reminder", "Your appointment on {{date}}",
     "<h1>Appointment Reminder</h1><p>Hi {{name}},</p><p>This is a reminder of "
     "your appointment with {{org}} on <b>{{date}}</b>. Reply to reschedule.</p>"),
    ("Restaurant", "Weekend Offer", "🍔 This weekend only — {{offer}}",
     "<h1>Weekend Special!</h1><p>Hi {{name}},</p><p>Enjoy <b>{{offer}}</b> at "
     "{{org}} this weekend. Show this email to redeem.</p>"
     "<p><a href=\"{{link}}\">Book a Table</a></p>"),
    ("Finance", "Invoice", "Invoice {{number}} from {{org}}",
     "<h1>Invoice {{number}}</h1><p>Hi {{name}},</p><p>Please find your invoice "
     "for <b>{{amount}}</b>, due {{date}}.</p><p><a href=\"{{link}}\">View &amp; "
     "Pay</a></p>"),
    ("Marketing", "Newsletter", "{{org}} Newsletter — {{month}}",
     "<h1>{{org}} Monthly Newsletter</h1><p>Hi {{name}},</p><p>Here's what's new "
     "this {{month}}. Thanks for being with us!</p><p><a href=\"{{link}}\">Read "
     "More</a></p>"),
    # Polished, real-world starters (header → body → bullets → CTA → footer with
    # the compliance tokens already in place).
    ("Marketing", "Announcement (clean)", "An important update from {{org}}",
     '<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
     '<table width="600" cellpadding="0" cellspacing="0" style="font-family:Arial,'
     'sans-serif;border:1px solid #e5e5e5">'
     '<tr><td style="background:#0b2a6b;padding:18px 24px;color:#fff;font-size:18px;'
     'font-weight:bold">{{org}}</td></tr>'
     '<tr><td style="padding:24px;color:#222;font-size:14px;line-height:1.6">'
     '<p>Dear {{name}},</p>'
     '<p>We have an important update to share with you about our services.</p>'
     '<p>Here is what it means for you:</p>'
     '<ul><li>Improved experience and faster service</li>'
     '<li>Greater transparency</li><li>Simpler processes</li></ul>'
     '<p style="text-align:center;margin:28px 0">'
     '<a href="{{link}}" style="background:#0b2a6b;color:#fff;padding:12px 28px;'
     'border-radius:4px;text-decoration:none">View Details</a></p>'
     '<p>Regards,<br>Team {{org}}</p></td></tr>'
     '<tr><td style="background:#0b2a6b;padding:14px 24px;color:#cdd7ee;font-size:11px;'
     'text-align:center">For any queries: helpdesk@{{org}}.com<br>'
     '<a href="{{view_in_browser_url}}" style="color:#cdd7ee">View in browser</a> &middot; '
     '<a href="{{unsubscribe_url}}" style="color:#cdd7ee">Unsubscribe</a></td></tr>'
     '</table></td></tr></table>'),
    ("Marketing", "Promo Offer (clean)", "{{name}}, your offer is waiting",
     '<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
     '<table width="560" cellpadding="0" cellspacing="0" style="font-family:Arial,'
     'sans-serif;border:1px solid #e5e5e5">'
     '<tr><td style="background:#4f46e5;padding:22px;color:#fff;text-align:center;'
     'font-size:20px;font-weight:bold">Special Offer Inside</td></tr>'
     '<tr><td style="padding:24px;color:#222;font-size:14px;line-height:1.6">'
     '<p>Hi {{name}},</p><p>Here is what you get:</p>'
     '<ul><li>Exclusive member benefits</li><li>Priority support</li>'
     '<li>Great value pricing</li></ul>'
     '<p style="text-align:center;margin:26px 0">'
     '<a href="{{link}}" style="background:#4f46e5;color:#fff;padding:12px 30px;'
     'border-radius:6px;text-decoration:none">View Offer</a></p>'
     '<p>Regards,<br>Team {{org}}</p></td></tr>'
     '<tr><td style="padding:14px;color:#888;font-size:11px;text-align:center">'
     'This is an auto-generated email.<br>'
     '<a href="{{view_in_browser_url}}">View in browser</a> &middot; '
     '<a href="{{unsubscribe_url}}">Unsubscribe</a></td></tr>'
     '</table></td></tr></table>'),
]


def seed_system_templates():
    """Install/refresh the starter library (idempotent — inserts any missing
    template by category+name, so new starters appear without duplicating)."""
    n = now()
    for category, name, subject, content in SYSTEM_TEMPLATE_SEED:
        exists = query("SELECT 1 FROM system_templates WHERE category=? AND name=?",
                       (category, name), one=True)
        if not exists:
            execute("INSERT INTO system_templates (category, name, subject, content,"
                    " published, created_at) VALUES (?,?,?,?,?,?)",
                    (category, name, subject, content, 1, n))


def seed_demo(account_id, user_email):
    """Populate a fresh account with realistic sample data so every screen
    has something to show on first login."""
    n = now()
    # contact list + contacts
    list_id = execute(
        "INSERT INTO contact_lists (account_id, name, created_at) VALUES (?,?,?)",
        (account_id, "Newsletter Subscribers", n),
    )
    sample_contacts = [
        ("sarah.chen@gmail.com", "Sarah Chen", "vip,newsletter", "active"),
        ("mike@acmecorp.com", "Mike Doyle", "lead", "active"),
        ("info@example.com", "Info Desk", "role", "blocked"),
        ("jdoe@yahoo.com", "Jane Doe", "newsletter", "active"),
        ("bounced@nodomain.invalid", "Old Address", "", "bounced"),
        ("unsub@gmail.com", "Tom Reed", "", "unsubscribed"),
    ]
    for email, name, tags, status in sample_contacts:
        execute(
            "INSERT INTO contacts (account_id, list_id, email, name, tags, status, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (account_id, list_id, email, name, tags, status, n),
        )
    # campaigns
    campaigns = [
        ("June Product Launch", "🚀 Big news inside", "Completed", 12500, 12500, 5840, 1920, 145),
        ("Weekly Digest #42", "Your weekly roundup", "Running", 8400, 5200, 2100, 640, 38),
        ("Win-back Offer", "We miss you — 30% off", "Scheduled", 3200, 0, 0, 0, 0),
        ("Black Friday Teaser", "Something big is coming", "Draft", 0, 0, 0, 0, 0),
    ]
    for name, subj, status, rcpt, sent, opens, clicks, bounces in campaigns:
        execute(
            "INSERT INTO campaigns (account_id, name, subject, status, recipients, sent, opens,"
            " clicks, bounces, from_email, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (account_id, name, subj, status, rcpt, sent, opens, clicks, bounces,
             user_email, n),
        )
    # smtp
    execute(
        "INSERT INTO smtp_servers (account_id, name, host, port, username, dedicated_ip,"
        " daily_limit, sent_today, warmup, health, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (account_id, "Primary Relay", "smtp.mailsaas.io", 587, "relay-01",
         "203.0.113.10", 50000, 18420, "Completed", "Healthy", n),
    )
    execute(
        "INSERT INTO smtp_servers (account_id, name, host, port, username, dedicated_ip,"
        " daily_limit, sent_today, warmup, health, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (account_id, "Warm-up Pool A", "smtp2.mailsaas.io", 587, "relay-02",
         "203.0.113.11", 5000, 940, "Day 6 of 14", "Warming", n),
    )
    # domains
    execute(
        "INSERT INTO domains (account_id, domain, spf, dkim, dmarc, verified, reputation,"
        " created_at) VALUES (?,?,?,?,?,?,?,?)",
        (account_id, "mailsaas.io", 1, 1, 1, 1, 94, n),
    )
    execute(
        "INSERT INTO domains (account_id, domain, spf, dkim, dmarc, verified, reputation,"
        " created_at) VALUES (?,?,?,?,?,?,?,?)",
        (account_id, "news.mailsaas.io", 1, 1, 0, 1, 78, n),
    )
    # invoices
    for i, amt in enumerate([0.0, 99.0, 99.0], start=1):
        execute(
            "INSERT INTO invoices (account_id, number, amount, status, created_at)"
            " VALUES (?,?,?,?,?)",
            (account_id, f"INV-2026-{1000+i}", amt, "Paid", n),
        )
    # a couple of verification samples
    for email, res, score, reason in [
        ("sarah.chen@gmail.com", "valid", 98, "Deliverable"),
        ("info@example.com", "risky", 55, "Role-based address"),
        ("foo@mailinator.com", "risky", 40, "Disposable domain"),
        ("typo@gmial.com", "invalid", 10, "No MX records"),
    ]:
        execute(
            "INSERT INTO verifications (account_id, email, result, score, reason, source,"
            " created_at) VALUES (?,?,?,?,?,?,?)",
            (account_id, email, res, score, reason, "single", n),
        )
    # templates
    for name, kind, subj in [
        ("Welcome Email", "Email", "Welcome to {{company}} 🎉"),
        ("Monthly Newsletter", "Email", "Your {{month}} roundup"),
        ("Flash Sale", "Email", "24 hours only — {{discount}}% off"),
        ("Hero Block", "Block", None),
    ]:
        execute(
            "INSERT INTO templates (account_id, name, kind, subject, content, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (account_id, name, kind, subj,
             "<h1>Hi {{name}}</h1><p>Your content here…</p>", n))
    # automations
    for name, trig, steps, status, enrolled in [
        ("Welcome Series", "Contact subscribes", 4, "Active", 1280),
        ("Drip Campaign", "Tag added: lead", 6, "Active", 540),
        ("Win-back", "No open in 60 days", 3, "Paused", 210),
        ("Birthday", "Date: birthday", 1, "Active", 95),
    ]:
        execute(
            "INSERT INTO automations (account_id, name, trigger, steps, status, enrolled,"
            " created_at) VALUES (?,?,?,?,?,?,?)",
            (account_id, name, trig, steps, status, enrolled, n))
    # landing pages
    for name, slug, status, views, subs in [
        ("Free Trial Signup", "free-trial", "Published", 8420, 612),
        ("Webinar Registration", "webinar-q3", "Published", 3110, 288),
        ("Ebook Download", "ebook-deliverability", "Draft", 0, 0),
    ]:
        execute(
            "INSERT INTO landing_pages (account_id, name, slug, status, views, submissions,"
            " created_at) VALUES (?,?,?,?,?,?,?)",
            (account_id, name, slug, status, views, subs, n))
    # webhook endpoint
    execute(
        "INSERT INTO webhooks (account_id, url, events, secret, active, last_status,"
        " deliveries, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (account_id, "https://example.com/webhooks/mailsaas",
         "Delivered,Opened,Clicked,Bounce", "whsec_" + str(account_id) + "demo",
         1, "200 OK", 18420, n))
    # a couple of sample complaints for the Complaint Center
    for email, kind in [("unsub@gmail.com", "unsubscribe"),
                        ("angry@yahoo.com", "complaint")]:
        execute("INSERT INTO complaints (account_id, campaign_id, email, kind, created_at)"
                " VALUES (?,?,?,?,?)", (account_id, None, email, kind, n))
    # the very first account on the platform is the super-admin
    if account_id == 1:
        execute("UPDATE accounts SET is_admin=1 WHERE id=1")
    log_activity(account_id, user_email, "Account created and demo data seeded")
