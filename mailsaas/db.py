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
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
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
    status       TEXT NOT NULL DEFAULT 'active',  -- active/unsubscribed/suppressed/bounced
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL,
    name         TEXT NOT NULL,
    subject      TEXT,
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
"""

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


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    _migrate()


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
        ("info@example.com", "Info Desk", "role", "suppressed"),
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
    # the very first account on the platform is the super-admin
    if account_id == 1:
        execute("UPDATE accounts SET is_admin=1 WHERE id=1")
    log_activity(account_id, user_email, "Account created and demo data seeded")
