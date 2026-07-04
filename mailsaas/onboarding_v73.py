"""
onboarding_v73.py — ZyvoMail guided onboarding (additive module, v73)

Implements the advanced first-run flow:
  signup extras capture → business profile → sending purpose → expected
  volume (plan + warm-up recommendation) → compliance check → domain setup
  status → launch checklist with a live Deliverability Readiness score.

Fully additive: registered from create_app() with one line, own migrations,
no changes to existing routes. Existing accounts are exempt (ob_done=1);
only accounts created after this version enter the wizard.
"""

import os
import re
import json
import secrets

from flask import (request, session, redirect, url_for, render_template,
                   jsonify, g)

try:
    from . import db as D          # package layout (python -m mailsaas.run)
except ImportError:                 # flat layout (python run.py from folder)
    import db as D

# --------------------------------------------------------------------------- #
#  Migrations (additive columns on accounts)
# --------------------------------------------------------------------------- #

_OB_MIGRATIONS = [
    ("accounts", "ob_done",          "INTEGER NOT NULL DEFAULT 1"),
    ("accounts", "ob_step",          "INTEGER NOT NULL DEFAULT 1"),
    ("accounts", "ob_business_type", "TEXT"),
    ("accounts", "ob_industry",      "TEXT"),
    ("accounts", "ob_size",          "TEXT"),
    ("accounts", "ob_gst",           "TEXT"),
    ("accounts", "ob_biz_email",     "TEXT"),
    ("accounts", "ob_logo",          "TEXT"),
    ("accounts", "ob_purpose",       "TEXT"),   # comma-separated keys
    ("accounts", "ob_volume",        "TEXT"),
    ("accounts", "ob_source",        "TEXT"),
    ("accounts", "ob_country",       "TEXT"),
    ("accounts", "ob_timezone",      "TEXT"),
    ("accounts", "ob_language",      "TEXT"),
    ("accounts", "ob_mobile",        "TEXT"),
]


def _migrate():
    dbc = D.get_db()
    for table, col, decl in _OB_MIGRATIONS:
        cols = [r["name"] for r in dbc.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            dbc.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    dbc.commit()


# --------------------------------------------------------------------------- #
#  Reference data (rendered by the wizard; single source of truth)
# --------------------------------------------------------------------------- #

BUSINESS_TYPES = ["Individual", "Startup", "Company", "Agency", "NGO",
                  "Government"]

INDUSTRIES = ["Technology / SaaS", "Real Estate", "Education", "Insurance",
              "Healthcare", "Finance / Banking", "E-commerce / Retail",
              "Manufacturing", "Travel & Hospitality", "Media & Events",
              "Consulting / Services", "Other"]

COMPANY_SIZES = ["Just me", "2–10", "11–50", "51–200", "201–1,000", "1,000+"]

PURPOSES = [
    ("marketing",     "Marketing campaigns",  "📣"),
    ("transactional", "Transactional emails", "🧾"),
    ("otp",           "OTP / verification",   "🔐"),
    ("newsletter",    "Newsletters",          "📰"),
    ("product",       "Product updates",      "🚀"),
    ("events",        "Event invitations",    "🎟️"),
    ("support",       "Customer support",     "💬"),
    ("internal",      "Internal emails",      "🏢"),
]

# volume key → (label, recommended plan, warm-up guidance)
VOLUMES = [
    ("v1",  "Less than 1,000 / month",  "Free",       "No warm-up needed — send right away."),
    ("v2",  "1,000 – 10,000",           "Starter",    "Light 1-week warm-up recommended."),
    ("v3",  "10,000 – 100,000",         "Growth",     "2-week warm-up schedule recommended."),
    ("v4",  "100,000 – 500,000",        "Pro",        "3-week warm-up with daily ramp-up."),
    ("v5",  "500,000 – 1 Million",      "Business",   "4-week warm-up + reputation monitoring."),
    ("v6",  "1 Million+",               "Enterprise", "4–6 week warm-up + dedicated IP pool."),
]

# source key → (label, stars 1..5, verdict, css tone)
SOURCES = [
    ("website",   "Website signup",     5, "Excellent — full consent trail.",        "good"),
    ("newsletter","Newsletter opt-in",  5, "Excellent — engaged subscribers.",       "good"),
    ("purchase",  "Purchase history",   4, "Good — existing business relationship.", "good"),
    ("crm",       "CRM / sales leads",  4, "Good — verify recency before sending.",  "good"),
    ("api",       "API / app signups",  4, "Good — keep double opt-in enabled.",     "good"),
    ("event",     "Event registration", 3, "Fair — send a re-permission email first.","warn"),
    ("other",     "Other",              2, "Review needed — confirm consent basis.", "warn"),
    ("purchased", "Purchased list",     1, "High spam risk — purchased lists damage sender reputation and violate most ESP policies. Strongly discouraged.", "bad"),
]

_GST_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")

LOGO_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads", "logos")


# --------------------------------------------------------------------------- #
#  Readiness score — computed from REAL account state, not wizard clicks
# --------------------------------------------------------------------------- #

def readiness(acct):
    aid = acct["id"]
    dom = D.query("SELECT * FROM domains WHERE account_id=? ORDER BY id DESC",
                  (aid,), one=True)
    contacts = D.query("SELECT COUNT(*) c FROM contacts WHERE account_id=?",
                       (aid,), one=True)["c"]
    tpl = D.query("SELECT COUNT(*) c FROM templates WHERE account_id=?",
                  (aid,), one=True)["c"]
    done = set(filter(None, (acct["onboarding"] or "").split(",")))
    src = next((s for s in SOURCES if s[0] == acct["ob_source"]), None)

    items = [
        ("Domain added",       15, bool(dom)),
        ("Domain verified",    10, bool(dom and dom["verified"])),
        ("SPF record",         10, bool(dom and dom["spf"])),
        ("DKIM record",        10, bool(dom and dom["dkim"])),
        ("DMARC record",       10, bool(dom and dom["dmarc"])),
        ("Contacts imported",  15, contacts > 0 or "contacts" in done),
        ("Template created",   10, tpl > 0 or "template" in done),
        ("Business profile",   10, bool(acct["ob_business_type"])),
        ("Sending purpose",     5, bool(acct["ob_purpose"])),
        ("Consent source OK",   5, bool(src and src[2] >= 3)),
    ]
    score = sum(w for _, w, ok in items if ok)
    return {"score": score, "items": [
        {"label": l, "points": w, "ok": bool(ok)} for l, w, ok in items]}


# --------------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------------- #

def register_onboarding(app, current_user, current_account):
    with app.app_context():
        try:
            _migrate()
        except Exception:
            pass  # first boot before schema exists; db.init runs _migrate paths

    os.makedirs(LOGO_DIR, exist_ok=True)

    # ---- capture extra signup fields + flag new accounts ------------------ #
    @app.before_request
    def _ob_capture_signup():
        if request.path == "/signup" and request.method == "POST":
            g._ob_extras = {
                "ob_country":  request.form.get("country", "India")[:60],
                "ob_timezone": request.form.get("timezone", "Asia/Kolkata")[:60],
                "ob_language": request.form.get("language", "English")[:30],
                "ob_mobile":   request.form.get("mobile", "")[:20],
            }

    @app.after_request
    def _ob_flag_new(resp):
        extras = getattr(g, "_ob_extras", None)
        if extras and session.get("uid") and resp.status_code in (301, 302):
            u = current_user()
            if u:
                sets = ", ".join(f"{k}=?" for k in extras)
                D.execute(f"UPDATE accounts SET ob_done=0, ob_step=1, {sets}"
                          " WHERE id=?", (*extras.values(), u["account_id"]))
        return resp

    # ---- funnel fresh accounts into the wizard ---------------------------- #
    _EXEMPT = ("/welcome", "/static", "/logout", "/login", "/signup",
               "/verify", "/api/", "/t/", "/2fa", "/forgot", "/reset")

    @app.before_request
    def _ob_funnel():
        if request.method != "GET":
            return
        p = request.path
        if any(p == x or p.startswith(x) for x in _EXEMPT):
            return
        acct = current_account()
        if acct and not acct["ob_done"] and not acct["is_admin"]:
            return redirect(url_for("ob_welcome"))

    # ---- wizard ------------------------------------------------------------ #
    @app.route("/welcome")
    def ob_welcome():
        acct = current_account()
        if not acct:
            return redirect(url_for("login"))
        u = current_user()
        return render_template(
            "onboarding.html", acct=acct, user=u,
            business_types=BUSINESS_TYPES, industries=INDUSTRIES,
            sizes=COMPANY_SIZES, purposes=PURPOSES, volumes=VOLUMES,
            sources=SOURCES, ready=readiness(acct),
            purpose_set=set(filter(None, (acct["ob_purpose"] or "").split(","))))

    @app.route("/welcome/save", methods=["POST"])
    def ob_save():
        acct = current_account()
        if not acct:
            return jsonify(ok=False), 401
        data = request.get_json(silent=True) or {}
        step = int(data.get("step", 0))
        aid = acct["id"]

        if step == 1:  # business profile
            bt = data.get("business_type", "")
            gst = (data.get("gst") or "").strip().upper()
            if bt not in BUSINESS_TYPES:
                return jsonify(ok=False, error="Choose a business type."), 400
            if gst and not _GST_RE.match(gst):
                return jsonify(ok=False,
                               error="That GST number doesn't look valid (15 characters, e.g. 33ABCDE1234F1Z5)."), 400
            be = (data.get("biz_email") or "").strip().lower()[:120]
            D.execute("UPDATE accounts SET ob_business_type=?, ob_industry=?,"
                      " ob_size=?, ob_gst=?, ob_biz_email=?, ob_step=2 WHERE id=?",
                      (bt, data.get("industry", "")[:60],
                       data.get("size", "")[:20], gst, be, aid))

        elif step == 2:  # sending purpose (multi)
            keys = [k for k in data.get("purposes", []) if
                    k in {p[0] for p in PURPOSES}]
            if not keys:
                return jsonify(ok=False, error="Pick at least one purpose."), 400
            D.execute("UPDATE accounts SET ob_purpose=?, ob_step=3 WHERE id=?",
                      (",".join(keys), aid))

        elif step == 3:  # volume
            v = data.get("volume", "")
            if v not in {x[0] for x in VOLUMES}:
                return jsonify(ok=False, error="Pick an expected volume."), 400
            D.execute("UPDATE accounts SET ob_volume=?, ob_step=4 WHERE id=?",
                      (v, aid))

        elif step == 4:  # compliance
            s = data.get("source", "")
            if s not in {x[0] for x in SOURCES}:
                return jsonify(ok=False, error="Tell us how the contacts were obtained."), 400
            D.execute("UPDATE accounts SET ob_source=?, ob_step=5 WHERE id=?",
                      (s, aid))

        elif step == 5:  # domain step viewed → advance
            D.execute("UPDATE accounts SET ob_step=6 WHERE id=?", (aid,))

        acct = current_account()
        return jsonify(ok=True, ready=readiness(acct))

    @app.route("/welcome/logo", methods=["POST"])
    def ob_logo():
        acct = current_account()
        if not acct:
            return jsonify(ok=False), 401
        f = request.files.get("logo")
        if not f or not f.filename:
            return jsonify(ok=False, error="No file selected."), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp", "svg"):
            return jsonify(ok=False, error="Use PNG, JPG, WEBP or SVG."), 400
        name = f"acct{acct['id']}_{secrets.token_hex(4)}.{ext}"
        f.save(os.path.join(LOGO_DIR, name))
        D.execute("UPDATE accounts SET ob_logo=? WHERE id=?", (name, acct["id"]))
        return jsonify(ok=True, url=url_for(
            "static", filename=f"uploads/logos/{name}"))

    @app.route("/welcome/finish", methods=["POST"])
    def ob_finish():
        acct = current_account()
        if acct:
            D.execute("UPDATE accounts SET ob_done=1 WHERE id=?", (acct["id"],))
            u = current_user()
            D.log_activity(acct["id"], u["email"] if u else "-",
                           "Completed guided onboarding")
        return jsonify(ok=True, next=url_for("dashboard"))

    @app.route("/welcome/skip", methods=["POST"])
    def ob_skip():
        acct = current_account()
        if acct:
            D.execute("UPDATE accounts SET ob_done=1 WHERE id=?", (acct["id"],))
        return jsonify(ok=True, next=url_for("dashboard"))


# =========================================================================== #
#  v73b — Login security + signup extras + success screen (additive)
# =========================================================================== #

from datetime import datetime, timedelta

LOCK_THRESHOLD = 5      # failures before temporary lock
LOCK_MINUTES = 15       # lock duration / rolling failure window

_OB_MIGRATIONS_B = [
    ("accounts", "ob_website",  "TEXT"),
    ("accounts", "ob_referral", "TEXT"),
]


def _migrate_b():
    dbc = D.get_db()
    for table, col, decl in _OB_MIGRATIONS_B:
        cols = [r["name"] for r in dbc.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            dbc.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    dbc.commit()


def _fail_state(email):
    """Failed logins for this email inside the rolling window, counted only
    after the most recent successful sign-in. Returns (fails, minutes_left)
    where minutes_left > 0 means the account is temporarily locked."""
    cutoff = (datetime.utcnow() - timedelta(minutes=LOCK_MINUTES)).strftime(
        "%Y-%m-%d %H:%M:%S")
    last_ok = D.query("SELECT created_at FROM login_history WHERE user_email=?"
                      " AND ok=1 ORDER BY id DESC LIMIT 1", (email,), one=True)
    since = cutoff
    if last_ok and last_ok["created_at"] > since:
        since = last_ok["created_at"]
    row = D.query("SELECT COUNT(*) c, MAX(created_at) m FROM login_history"
                  " WHERE user_email=? AND ok=0 AND created_at>=?",
                  (email, since), one=True)
    fails = row["c"] or 0
    minutes_left = 0
    if fails >= LOCK_THRESHOLD and row["m"]:
        unlock = (datetime.strptime(row["m"], "%Y-%m-%d %H:%M:%S")
                  + timedelta(minutes=LOCK_MINUTES))
        delta = (unlock - datetime.utcnow()).total_seconds()
        minutes_left = max(0, int(delta // 60) + (1 if delta % 60 else 0))
    return fails, minutes_left


def _parse_agent(agent):
    """Human-readable browser + OS from a User-Agent string."""
    a = agent or ""
    if "Edg/" in a or "Edge" in a:
        browser = "Edge"
    elif "OPR/" in a or "Opera" in a:
        browser = "Opera"
    elif "Firefox" in a:
        browser = "Firefox"
    elif "Chrome" in a:
        browser = "Chrome"
    elif "Safari" in a:
        browser = "Safari"
    else:
        browser = "Unknown browser"
    if "Windows NT 10" in a:
        os_name = "Windows 10 / 11"
    elif "Windows" in a:
        os_name = "Windows"
    elif "Mac OS X" in a or "Macintosh" in a:
        os_name = "macOS"
    elif "Android" in a:
        os_name = "Android"
    elif "iPhone" in a or "iPad" in a:
        os_name = "iOS"
    elif "Linux" in a:
        os_name = "Linux"
    else:
        os_name = ""
    return browser, os_name


def _when_label(ts):
    try:
        d = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts
    days = (datetime.utcnow().date() - d.date()).days
    if days == 0:
        return "Today " + d.strftime("%H:%M UTC")
    if days == 1:
        return "Yesterday " + d.strftime("%H:%M UTC")
    return d.strftime("%d %b %Y")


def register_auth_extras(app, current_user, current_account):
    with app.app_context():
        try:
            _migrate_b()
        except Exception:
            pass

    # ---- extend signup capture: website / industry / referral / logo ------ #
    @app.before_request
    def _ob_capture_signup_b():
        if request.path == "/signup" and request.method == "POST":
            extras = getattr(g, "_ob_extras", None)
            if extras is None:
                extras = g._ob_extras = {}
            site = (request.form.get("website") or "").strip()[:120]
            site = re.sub(r"^https?://", "", site).rstrip("/")
            extras["ob_website"] = site
            extras["ob_referral"] = (request.form.get("referral") or "").strip()[:40]
            ind = (request.form.get("industry") or "").strip()[:60]
            if ind:
                extras["ob_industry"] = ind
            f = request.files.get("logo")
            if f and f.filename:
                ext = f.filename.rsplit(".", 1)[-1].lower()
                if ext in ("png", "jpg", "jpeg", "webp", "svg"):
                    data = f.read(2 * 1024 * 1024 + 1)
                    if len(data) <= 2 * 1024 * 1024:
                        g._ob_logo = (ext, data)

    @app.after_request
    def _ob_save_logo(resp):
        logo = getattr(g, "_ob_logo", None)
        if logo and session.get("uid") and resp.status_code in (301, 302):
            u = current_user()
            if u:
                ext, data = logo
                name = f"acct{u['account_id']}_{secrets.token_hex(4)}.{ext}"
                with open(os.path.join(LOGO_DIR, name), "wb") as fh:
                    fh.write(data)
                D.execute("UPDATE accounts SET ob_logo=? WHERE id=?",
                          (name, u["account_id"]))
        return resp

    # ---- send fresh signups to the success screen, not the dashboard ------ #
    @app.after_request
    def _ob_success_redirect(resp):
        if (getattr(g, "_ob_extras", None) is not None and session.get("uid")
                and resp.status_code in (301, 302)
                and (resp.location or "").endswith("/dashboard")):
            resp.location = url_for("ob_success")
        return resp

    # ---- login lockout: 5 failures → locked for 15 minutes ---------------- #
    @app.before_request
    def _login_guard():
        if request.path != "/login" or request.method != "POST":
            return
        if app.config.get("TESTING"):
            return
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            return
        fails, minutes_left = _fail_state(email)
        if minutes_left > 0:
            g._login_locked = minutes_left
            from flask import flash, render_template as rt
            flash(f"Too many failed attempts. This account is temporarily "
                  f"locked — try again in {minutes_left} minute"
                  f"{'s' if minutes_left != 1 else ''}.", "error")
            return rt("login.html"), 429
        g._login_prior_fails = fails

    # ---- template context: attempts remaining + last-login device info ---- #
    @app.context_processor
    def _auth_ctx():
        info = None
        prior = getattr(g, "_login_prior_fails", None)
        if prior is not None:
            remaining = max(0, LOCK_THRESHOLD - (prior + 1))
            info = {"remaining": remaining, "threshold": LOCK_THRESHOLD,
                    "lock_minutes": LOCK_MINUTES}
        last = None
        u = current_user()
        if u:
            rows = D.query("SELECT ip, agent, created_at FROM login_history"
                           " WHERE user_email=? AND ok=1 ORDER BY id DESC"
                           " LIMIT 2", (u["email"],))
            if rows and len(rows) > 1:
                r = rows[1]  # previous sign-in (latest row is this session)
                browser, os_name = _parse_agent(r["agent"])
                last = {"browser": browser, "os": os_name,
                        "when": _when_label(r["created_at"]),
                        "ip": r["ip"] or "-"}
        return {"login_fail_info": info,
                "login_locked_minutes": getattr(g, "_login_locked", 0),
                "last_login_info": last}

    # ---- post-signup success screen + resend verification ----------------- #
    @app.route("/welcome-success")
    def ob_success():
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        link = None
        if not u["verified"] and u["verify_token"]:
            link = url_for("verify_email", token=u["verify_token"])
        return render_template("welcome_success.html", u=u, verify_link=link)

    @app.route("/resend-verification", methods=["POST"])
    def ob_resend():
        u = current_user()
        if not u:
            return jsonify(ok=False), 401
        if u["verified"]:
            return jsonify(ok=True, verified=True)
        token = u["verify_token"] or secrets.token_urlsafe(24)
        D.execute("UPDATE users SET verify_token=? WHERE id=?", (token, u["id"]))
        # No outbound mail in this build — return the link so the flow is
        # testable end to end. In production this is emailed instead.
        return jsonify(ok=True, link=url_for("verify_email", token=token))


# =========================================================================== #
#  v73d — Magic link · auto-login verify · trusted devices · 2FA backup
#          codes · guided "Basic setup" experience (Mailercloud-style)
# =========================================================================== #

import hashlib
from flask import flash


def _migrate_d():
    dbc = D.get_db()
    ucols = [r["name"] for r in dbc.execute("PRAGMA table_info(users)")]
    for col, decl in [("magic_token", "TEXT"), ("magic_expires", "TEXT")]:
        if col not in ucols:
            dbc.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
    dbc.execute("""CREATE TABLE IF NOT EXISTS trusted_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL,
        agent TEXT,
        created_at TEXT NOT NULL,
        expires TEXT NOT NULL)""")
    dbc.execute("""CREATE TABLE IF NOT EXISTS twofa_backup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code_hash TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL)""")
    dbc.commit()


def _h(s):
    return hashlib.sha256(("zyvo:" + s).encode()).hexdigest()


def _login_now(u):
    """Complete a login using the app's canonical helper (session token,
    activity log, login history)."""
    try:
        from . import app as APP
    except ImportError:
        import app as APP
    APP._complete_login(u)


def _nav_steps(is_admin):
    try:
        from .nav import USER_ONBOARDING_STEPS, ADMIN_ONBOARDING_STEPS
    except ImportError:
        from nav import USER_ONBOARDING_STEPS, ADMIN_ONBOARDING_STEPS
    return ADMIN_ONBOARDING_STEPS if is_admin else USER_ONBOARDING_STEPS


APP_VERSION = "v82"


def register_experience(app, current_user, current_account):
    with app.app_context():
        try:
            _migrate_d()
        except Exception:
            pass
    # Enterprise pass: default admin credentials are no longer shown in the
    # UI. Surface them on the server console instead (dev convenience).
    if not app.config.get("TESTING"):
        print("[ZyvoMail] Default admin sign-in: admin / admin@123 "
              "(change it in Settings -> Security)")

    # ---- context: IST greeting + sidebar setup progress + version --------- #
    @app.context_processor
    def _exp_ctx():
        h = (datetime.utcnow() + timedelta(hours=5, minutes=30)).hour
        if 5 <= h < 12:
            greet = "Good morning"
        elif 12 <= h < 17:
            greet = "Good afternoon"
        elif 17 <= h < 22:
            greet = "Good evening"
        else:
            greet = "Welcome back"
        prog = None
        acct = current_account()
        if acct:
            steps = _nav_steps(acct["is_admin"])
            done = set(filter(None, (acct["onboarding"] or "").split(",")))
            d = len([s for s in steps if s[0] in done])
            t = len(steps) or 1
            prog = {"done": d, "total": len(steps), "pct": int(d * 100 / t)}
        return {"greeting_ist": greet, "setup_progress": prog,
                "APP_VERSION": APP_VERSION}

    # ---- skip the guided setup checklist ----------------------------------- #
    @app.route("/dashboard/skip-setup", methods=["POST"])
    def skip_setup():
        acct = current_account()
        if acct:
            for step in _nav_steps(acct["is_admin"]):
                D.mark_onboarding(acct["id"], step[0])
        return redirect(url_for("dashboard"))

    # ---- magic-link sign in ------------------------------------------------ #
    @app.route("/magic-link", methods=["POST"])
    def magic_link():
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        out = {"ok": True,
               "msg": "If an account exists for that email, a sign-in link has been sent."}
        if email:
            u = D.query("SELECT * FROM users WHERE email=?", (email,), one=True)
            if u:
                tok = secrets.token_urlsafe(24)
                exp = (datetime.utcnow() + timedelta(minutes=15)).strftime(
                    "%Y-%m-%d %H:%M:%S")
                D.execute("UPDATE users SET magic_token=?, magic_expires=?"
                          " WHERE id=?", (tok, exp, u["id"]))
                # Dev build: surface the link so the flow is testable without
                # outbound mail. Set MAGIC_LINK_DEV=False in production —
                # the link must then only ever be EMAILED to the address.
                if app.config.get("MAGIC_LINK_DEV", True):
                    out["dev_link"] = url_for("magic_login", token=tok)
        return jsonify(**out)

    @app.route("/magic/<token>")
    def magic_login(token):
        u = D.query("SELECT * FROM users WHERE magic_token=?", (token,),
                    one=True)
        if (not u or not u["magic_expires"]
                or u["magic_expires"] < D.now()):
            flash("That sign-in link is invalid or has expired.", "error")
            return redirect(url_for("login"))
        D.execute("UPDATE users SET magic_token=NULL, magic_expires=NULL"
                  " WHERE id=?", (u["id"],))
        if u["twofa"]:
            session["pending_uid"] = u["id"]
            return redirect(url_for("twofa_challenge"))
        _login_now(u)
        D.log_activity(u["account_id"], u["email"], "Signed in via magic link")
        return redirect(url_for("dashboard"))

    # ---- auto-login when the email-verification link is opened ------------- #
    @app.before_request
    def _verify_autologin():
        if not request.path.startswith("/verify-email/"):
            return
        token = request.path.rsplit("/", 1)[-1]
        u = D.query("SELECT * FROM users WHERE verify_token=?", (token,),
                    one=True)
        if not u:
            return  # fall through to the original route's invalid-link flash
        D.execute("UPDATE users SET verified=1, verify_token=NULL WHERE id=?",
                  (u["id"],))
        D.log_activity(u["account_id"], u["email"], "Verified email address")
        if not current_user():
            if u["twofa"]:
                session["pending_uid"] = u["id"]
                flash("Email verified ✔ — enter your 2FA code to continue.",
                      "success")
                return redirect(url_for("twofa_challenge"))
            _login_now(u)
            flash("Email verified ✔ — welcome to ZyvoMail!", "success")
        else:
            flash("Email verified ✔", "success")
        return redirect(url_for("dashboard"))

    # ---- 2FA: trusted-device skip + backup-code acceptance ----------------- #
    @app.before_request
    def _twofa_shortcuts():
        if request.path != "/2fa":
            return
        pending = session.get("pending_uid")
        if not pending:
            return
        u = D.query("SELECT * FROM users WHERE id=?", (pending,), one=True)
        if not u:
            return
        # trusted device → skip the challenge entirely
        tok = request.cookies.get("zv_trust")
        if tok:
            row = D.query("SELECT id FROM trusted_devices WHERE user_id=? AND"
                          " token_hash=? AND expires>?",
                          (u["id"], _h(tok), D.now()), one=True)
            if row:
                nxt = session.get("next") or url_for("dashboard")
                _login_now(u)
                D.log_activity(u["account_id"], u["email"],
                               "Signed in (trusted device — 2FA skipped)")
                return redirect(nxt)
        # backup code entered instead of a TOTP code
        if request.method == "POST":
            code = (request.form.get("code") or "").strip().upper()
            code = code.replace(" ", "")
            if "-" in code and len(code) >= 9:
                row = D.query("SELECT id FROM twofa_backup WHERE user_id=? AND"
                              " code_hash=? AND used=0",
                              (u["id"], _h(code)), one=True)
                if row:
                    D.execute("UPDATE twofa_backup SET used=1 WHERE id=?",
                              (row["id"],))
                    nxt = session.get("next") or url_for("dashboard")
                    _login_now(u)
                    D.log_activity(u["account_id"], u["email"],
                                   "Signed in with a 2FA backup code")
                    return redirect(nxt)
                flash("Invalid backup code.", "error")

    @app.after_request
    def _twofa_trust(resp):
        # set the trusted-device cookie after a successful challenge
        if (request.path == "/2fa" and request.method == "POST"
                and resp.status_code == 302
                and "/2fa" not in (resp.location or "")
                and request.form.get("remember_device")
                and session.get("uid")):
            tok = secrets.token_urlsafe(24)
            exp = (datetime.utcnow() + timedelta(days=30)).strftime(
                "%Y-%m-%d %H:%M:%S")
            D.execute("INSERT INTO trusted_devices (user_id, token_hash,"
                      " agent, created_at, expires) VALUES (?,?,?,?,?)",
                      (session["uid"], _h(tok),
                       request.headers.get("User-Agent", "")[:200],
                       D.now(), exp))
            resp.set_cookie("zv_trust", tok, max_age=30 * 86400,
                            httponly=True, samesite="Lax")
        return resp

    # ---- 2FA backup codes: generate (shown once) --------------------------- #
    @app.route("/security/backup-codes", methods=["POST"])
    def backup_codes():
        u = current_user()
        if not u:
            return jsonify(ok=False), 401
        if not u["twofa"]:
            return jsonify(ok=False, error="Enable 2FA first."), 400
        codes = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
                 for _ in range(8)]
        D.execute("DELETE FROM twofa_backup WHERE user_id=?", (u["id"],))
        for c in codes:
            D.execute("INSERT INTO twofa_backup (user_id, code_hash, used,"
                      " created_at) VALUES (?,?,0,?)", (u["id"], _h(c), D.now()))
        D.log_activity(u["account_id"], u["email"],
                       "Generated new 2FA backup codes")
        return jsonify(ok=True, codes=codes)


# =========================================================================== #
#  v73f — Real OAuth sign-in (Google · Microsoft, authorization-code flow)
#          Buttons appear only when client credentials are configured.
# =========================================================================== #

import json as _json
import urllib.parse
import urllib.request

OAUTH_PROVIDERS = {
    "google": {
        "auth":     "https://accounts.google.com/o/oauth2/v2/auth",
        "token":    "https://oauth2.googleapis.com/token",
        "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope":    "openid email profile",
        "id_env":   "GOOGLE_CLIENT_ID",
        "sec_env":  "GOOGLE_CLIENT_SECRET",
        "label":    "Google",
    },
    "microsoft": {
        "auth":     "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token":    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo": "https://graph.microsoft.com/oidc/userinfo",
        "scope":    "openid email profile",
        "id_env":   "MS_CLIENT_ID",
        "sec_env":  "MS_CLIENT_SECRET",
        "label":    "Microsoft",
    },
}


def _oauth_cfg(app, provider):
    p = OAUTH_PROVIDERS.get(provider)
    if not p:
        return None
    cid = app.config.get(p["id_env"]) or os.environ.get(p["id_env"], "")
    sec = app.config.get(p["sec_env"]) or os.environ.get(p["sec_env"], "")
    if not (cid and sec):
        return None
    return {**p, "client_id": cid, "client_secret": sec}


def _migrate_f():
    dbc = D.get_db()
    ucols = [r["name"] for r in dbc.execute("PRAGMA table_info(users)")]
    for col, decl in [("oauth_provider", "TEXT"), ("oauth_sub", "TEXT")]:
        if col not in ucols:
            dbc.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
    dbc.commit()


def _http_post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return _json.loads(r.read().decode())


def _http_get_bearer(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return _json.loads(r.read().decode())


def register_oauth(app, current_user, current_account):
    with app.app_context():
        try:
            _migrate_f()
        except Exception:
            pass

    @app.context_processor
    def _oauth_ctx():
        return {"oauth_enabled": {
            k: bool(_oauth_cfg(app, k)) for k in OAUTH_PROVIDERS}}

    @app.route("/auth/<provider>")
    def oauth_start(provider):
        cfg = _oauth_cfg(app, provider)
        if not cfg:
            flash("That sign-in method is not configured yet.", "error")
            return redirect(url_for("login"))
        state = secrets.token_urlsafe(16)
        session["oauth_state"] = state
        session["oauth_provider"] = provider
        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": url_for("oauth_callback", provider=provider,
                                    _external=True),
            "response_type": "code",
            "scope": cfg["scope"],
            "state": state,
        }
        return redirect(cfg["auth"] + "?" + urllib.parse.urlencode(params))

    @app.route("/auth/<provider>/callback")
    def oauth_callback(provider):
        cfg = _oauth_cfg(app, provider)
        state_ok = (request.args.get("state")
                    and request.args.get("state") == session.pop("oauth_state", None))
        code = request.args.get("code")
        if not (cfg and state_ok and code):
            flash("Sign-in was cancelled or the request was invalid.", "error")
            return redirect(url_for("login"))
        try:
            tok = _http_post_form(cfg["token"], {
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": url_for("oauth_callback", provider=provider,
                                        _external=True),
            })
            info = _http_get_bearer(cfg["userinfo"], tok["access_token"])
        except Exception:
            flash(f"Could not complete {cfg['label']} sign-in. Please try "
                  "again or use your email and password.", "error")
            return redirect(url_for("login"))

        email = (info.get("email") or "").strip().lower()
        sub = str(info.get("sub") or "")
        name = (info.get("name") or email.split("@")[0] or "User").strip()
        if not email:
            flash(f"{cfg['label']} did not share an email address for your "
                  "account, so we can't sign you in this way.", "error")
            return redirect(url_for("login"))

        u = D.query("SELECT * FROM users WHERE email=?", (email,), one=True)
        if u is None:
            # First time here → create a workspace (same shape as /signup).
            try:
                from . import app as APP
            except ImportError:
                import app as APP
            import bcrypt as _bcrypt
            acct_id = D.execute(
                "INSERT INTO accounts (name, plan, credits, created_at)"
                " VALUES (?,?,?,?)",
                (f"{name}'s Workspace", "Free", 1000, D.now()))
            random_pw = secrets.token_urlsafe(24)
            pw_hash = _bcrypt.hashpw(random_pw.encode(),
                                     _bcrypt.gensalt()).decode()
            uid = D.execute(
                "INSERT INTO users (account_id, email, name, pw_hash, role,"
                " created_at, last_login, verified, verify_token,"
                " oauth_provider, oauth_sub)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (acct_id, email, name, pw_hash, "Owner", D.now(), D.now(),
                 1, None, provider, sub))  # provider verified the email
            D.seed_demo(acct_id, email)
            D.execute("UPDATE accounts SET ob_done=0, ob_step=1 WHERE id=?",
                      (acct_id,))
            u = D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
            _login_now(u)
            D.log_activity(acct_id, email,
                           f"Account created via {cfg['label']} sign-in")
            return redirect(url_for("ob_welcome"))

        # Existing user → link identity on first OAuth use, honour 2FA.
        if not u["oauth_sub"]:
            D.execute("UPDATE users SET oauth_provider=?, oauth_sub=?"
                      " WHERE id=?", (provider, sub, u["id"]))
        if u["twofa"]:
            session["pending_uid"] = u["id"]
            return redirect(url_for("twofa_challenge"))
        _login_now(u)
        D.log_activity(u["account_id"], u["email"],
                       f"Signed in via {cfg['label']}")
        return redirect(url_for("dashboard"))


# ---- v73f: recent activity feed for the dashboard ------------------------- #
def register_activity_feed(app, current_user, current_account):
    @app.context_processor
    def _activity_ctx():
        if request.endpoint != "dashboard":
            return {}
        acct = current_account()
        if not acct:
            return {}
        rows = D.query("SELECT actor, action, created_at FROM activity"
                       " WHERE account_id=? ORDER BY id DESC LIMIT 6",
                       (acct["id"],))
        return {"recent_activity": [
            {"actor": r["actor"] or "—", "action": r["action"],
             "when": _when_label(r["created_at"])} for r in (rows or [])]}
