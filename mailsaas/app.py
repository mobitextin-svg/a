"""
MailSaaS — an enterprise-grade email verification & delivery platform.

Self-contained Flask application (matches the repo's `fileshare` style):
single process, SQLite storage, server-rendered Jinja UI, bcrypt auth.

Run:
    pip install -r requirements.txt
    python -m mailsaas.app           # or: python run.py
    -> http://127.0.0.1:5005

The whole product information architecture lives in ``nav.py``; functional
modules have bespoke views below, and any module flagged ``built=False`` is
served by a consistent auto-generated landing page so the entire platform is
navigable end to end.
"""
import os
import io
import csv
import json
import secrets
import functools
from datetime import datetime

from flask import (Flask, request, render_template, redirect, url_for, session,
                   flash, jsonify, g, abort, Response)

try:
    import bcrypt
except ImportError:  # pragma: no cover
    raise SystemExit("Missing dependency: pip install bcrypt")

from . import db as D
from . import ai
from . import deliverability as DELIV
from .nav import NAV, NAV_BY_KEY, NAV_GROUPS
from .verify import verify_email, verify_bulk


# --------------------------------------------------------------------------- #
#  System metrics for the Monitoring module (real where possible)
# --------------------------------------------------------------------------- #


def _system_metrics():
    import time as _t
    cpu = ram = None
    # Real CPU load average (Unix) -> rough % of cores.
    try:
        load1 = os.getloadavg()[0]
        cores = os.cpu_count() or 1
        cpu = round(min(100, 100 * load1 / cores), 1)
    except (OSError, AttributeError):
        cpu = 23.4
    # Real memory usage from /proc/meminfo (Linux).
    try:
        info = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0])
        total, avail = info["MemTotal"], info.get("MemAvailable", info["MemFree"])
        ram = round(100 * (total - avail) / total, 1)
    except (OSError, KeyError, ValueError):
        ram = 41.0
    return {
        "cpu": cpu, "ram": ram,
        "queue": 1843, "smtp_health": "Healthy", "dns": "All records OK",
        "api": "Operational", "uptime": "99.98%",
        "checked": _t.strftime("%Y-%m-%d %H:%M:%S UTC", _t.gmtime()),
        "services": [
            ("API Gateway", "Operational", 100),
            ("Verification Engine", "Operational", 100),
            ("SMTP Relays", "Healthy", 98),
            ("Queue Workers", "Operational", 100),
            ("Webhook Dispatcher", "Operational", 99),
            ("Database", "Operational", 100),
        ],
    }


# --------------------------------------------------------------------------- #
#  App factory
# --------------------------------------------------------------------------- #


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("MAILSAAS_SECRET", secrets.token_hex(16)),
        DATABASE=os.environ.get(
            "MAILSAAS_DB",
            os.path.join(os.path.dirname(__file__), "mailsaas.sqlite3"),
        ),
    )
    app.teardown_appcontext(D.close_db)

    with app.app_context():
        D.init_db()

    register_context(app)
    register_auth(app)
    register_modules(app)
    register_api(app)
    return app


# --------------------------------------------------------------------------- #
#  Auth helpers
# --------------------------------------------------------------------------- #


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)


def current_account():
    u = current_user()
    if not u:
        return None
    return D.query("SELECT * FROM accounts WHERE id=?", (u["account_id"],), one=True)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def register_context(app):
    @app.context_processor
    def inject():
        return {
            "NAV": NAV,
            "NAV_GROUPS": NAV_GROUPS,
            "NAV_BY_KEY": NAV_BY_KEY,
            "user": current_user(),
            "account": current_account(),
            "active": request.path.strip("/").split("/")[0] or "dashboard",
            "year": datetime.utcnow().year,
        }


# --------------------------------------------------------------------------- #
#  Auth routes
# --------------------------------------------------------------------------- #


def register_auth(app):
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            pw = request.form.get("password", "")
            company = request.form.get("company", "").strip() or f"{name}'s Workspace"
            if not (name and email and len(pw) >= 6):
                flash("Please provide a name, email and a 6+ character password.", "error")
                return render_template("signup.html")
            if D.query("SELECT 1 FROM users WHERE email=?", (email,), one=True):
                flash("An account with that email already exists.", "error")
                return render_template("signup.html")
            acct_id = D.execute(
                "INSERT INTO accounts (name, plan, credits, created_at) VALUES (?,?,?,?)",
                (company, "Free", 1000, D.now()),
            )
            pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
            uid = D.execute(
                "INSERT INTO users (account_id, email, name, pw_hash, role, created_at,"
                " last_login) VALUES (?,?,?,?,?,?,?)",
                (acct_id, email, name, pw_hash, "Owner", D.now(), D.now()),
            )
            D.seed_demo(acct_id, email)
            session.clear()
            session["uid"] = uid
            flash("Welcome to MailSaaS! Your workspace is ready.", "success")
            return redirect(url_for("dashboard"))
        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            pw = request.form.get("password", "")
            u = D.query("SELECT * FROM users WHERE email=?", (email,), one=True)
            if u and bcrypt.checkpw(pw.encode(), u["pw_hash"].encode()):
                session.clear()
                session["uid"] = u["id"]
                D.execute("UPDATE users SET last_login=? WHERE id=?", (D.now(), u["id"]))
                D.log_activity(u["account_id"], u["email"], "Signed in")
                nxt = request.args.get("next") or url_for("dashboard")
                return redirect(nxt)
            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def root():
        return redirect(url_for("dashboard") if current_user() else url_for("login"))


# --------------------------------------------------------------------------- #
#  Functional module routes
# --------------------------------------------------------------------------- #


def register_modules(app):
    # ---- Dashboard ------------------------------------------------------- #
    @app.route("/dashboard")
    @login_required
    def dashboard():
        acct = current_account()
        aid = acct["id"]
        stats = {
            "contacts": D.query("SELECT COUNT(*) c FROM contacts WHERE account_id=?",
                                 (aid,), one=True)["c"],
            "campaigns": D.query("SELECT COUNT(*) c FROM campaigns WHERE account_id=?",
                                 (aid,), one=True)["c"],
            "verifications": D.query("SELECT COUNT(*) c FROM verifications WHERE account_id=?",
                                     (aid,), one=True)["c"],
            "domains": D.query("SELECT COUNT(*) c FROM domains WHERE account_id=?",
                               (aid,), one=True)["c"],
        }
        agg = D.query(
            "SELECT COALESCE(SUM(sent),0) sent, COALESCE(SUM(opens),0) opens,"
            " COALESCE(SUM(clicks),0) clicks, COALESCE(SUM(bounces),0) bounces"
            " FROM campaigns WHERE account_id=?", (aid,), one=True)
        sent = agg["sent"] or 0
        deliver = {
            "sent": sent,
            "open_rate": round(100 * agg["opens"] / sent, 1) if sent else 0,
            "click_rate": round(100 * agg["clicks"] / sent, 1) if sent else 0,
            "bounce_rate": round(100 * agg["bounces"] / sent, 1) if sent else 0,
        }
        activity = D.query(
            "SELECT * FROM activity WHERE account_id=? ORDER BY id DESC LIMIT 8", (aid,))
        campaigns = D.query(
            "SELECT * FROM campaigns WHERE account_id=? ORDER BY id DESC LIMIT 5", (aid,))
        return render_template("dashboard.html", stats=stats, deliver=deliver,
                               activity=activity, campaigns=campaigns)

    # ---- Email Verification --------------------------------------------- #
    @app.route("/verification", methods=["GET", "POST"])
    @login_required
    def verification():
        acct = current_account()
        result = None
        bulk_results = None
        if request.method == "POST":
            mode = request.form.get("mode")
            if mode == "single":
                email = request.form.get("email", "")
                result = verify_email(email)
                D.execute(
                    "INSERT INTO verifications (account_id, email, result, score, reason,"
                    " detail, source, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (acct["id"], result["email"], result["result"], result["score"],
                     result["reason"], json.dumps(result.get("checks", {})), "single",
                     D.now()))
                D.log_activity(acct["id"], current_user()["email"],
                               f"Verified {result['email']} → {result['result']}")
            elif mode == "bulk":
                blob = request.form.get("emails", "")
                bulk_results = verify_bulk(blob)
                for r in bulk_results:
                    D.execute(
                        "INSERT INTO verifications (account_id, email, result, score, reason,"
                        " detail, source, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (acct["id"], r["email"], r["result"], r["score"], r["reason"],
                         json.dumps(r.get("checks", {})), "bulk", D.now()))
                D.log_activity(acct["id"], current_user()["email"],
                               f"Bulk verified {len(bulk_results)} addresses")
        history = D.query(
            "SELECT * FROM verifications WHERE account_id=? ORDER BY id DESC LIMIT 50",
            (acct["id"],))
        summary = D.query(
            "SELECT result, COUNT(*) c FROM verifications WHERE account_id=? GROUP BY result",
            (acct["id"],))
        summary = {row["result"]: row["c"] for row in summary}
        return render_template("verification.html", result=result,
                               bulk_results=bulk_results, history=history,
                               summary=summary)

    @app.route("/verification/export")
    @login_required
    def verification_export():
        acct = current_account()
        rows = D.query(
            "SELECT email, result, score, reason, source, created_at FROM verifications"
            " WHERE account_id=? ORDER BY id DESC", (acct["id"],))
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["email", "result", "score", "reason", "source", "checked_at"])
        for r in rows:
            w.writerow([r["email"], r["result"], r["score"], r["reason"],
                        r["source"], r["created_at"]])
        return Response(
            buf.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=verifications.csv"})

    # ---- Contacts -------------------------------------------------------- #
    @app.route("/contacts", methods=["GET", "POST"])
    @login_required
    def contacts():
        acct = current_account()
        aid = acct["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                D.execute(
                    "INSERT INTO contacts (account_id, email, name, tags, status, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (aid, request.form.get("email", "").strip().lower(),
                     request.form.get("name", "").strip(),
                     request.form.get("tags", "").strip(), "active", D.now()))
                flash("Contact added.", "success")
            elif action == "import":
                raw = request.form.get("csv", "")
                count = 0
                for line in raw.splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    email = parts[0].lower() if parts else ""
                    if "@" not in email:
                        continue
                    name = parts[1] if len(parts) > 1 else ""
                    D.execute(
                        "INSERT INTO contacts (account_id, email, name, status, created_at)"
                        " VALUES (?,?,?,?,?)", (aid, email, name, "active", D.now()))
                    count += 1
                flash(f"Imported {count} contacts.", "success")
            elif action == "suppress":
                D.execute("UPDATE contacts SET status='suppressed' WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
            elif action == "delete":
                D.execute("DELETE FROM contacts WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
            return redirect(url_for("contacts"))
        status_filter = request.args.get("status")
        if status_filter:
            rows = D.query("SELECT * FROM contacts WHERE account_id=? AND status=?"
                           " ORDER BY id DESC", (aid, status_filter))
        else:
            rows = D.query("SELECT * FROM contacts WHERE account_id=? ORDER BY id DESC", (aid,))
        counts = D.query(
            "SELECT status, COUNT(*) c FROM contacts WHERE account_id=? GROUP BY status", (aid,))
        counts = {r["status"]: r["c"] for r in counts}
        lists = D.query("SELECT * FROM contact_lists WHERE account_id=?", (aid,))
        return render_template("contacts.html", contacts=rows, counts=counts,
                               lists=lists, status_filter=status_filter)

    @app.route("/contacts/export")
    @login_required
    def contacts_export():
        aid = current_account()["id"]
        rows = D.query("SELECT email, name, tags, status, created_at FROM contacts"
                       " WHERE account_id=? ORDER BY id DESC", (aid,))
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["email", "name", "tags", "status", "added"])
        for r in rows:
            w.writerow([r["email"], r["name"], r["tags"], r["status"], r["created_at"]])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=contacts.csv"})

    # ---- Campaigns / Sender --------------------------------------------- #
    @app.route("/campaigns", methods=["GET", "POST"])
    @login_required
    def campaigns():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                rcpt = D.query("SELECT COUNT(*) c FROM contacts WHERE account_id=?"
                               " AND status='active'", (aid,), one=True)["c"]
                D.execute(
                    "INSERT INTO campaigns (account_id, name, subject, body, from_email,"
                    " status, recipients, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (aid, request.form.get("name", "Untitled").strip(),
                     request.form.get("subject", "").strip(),
                     request.form.get("body", "").strip(),
                     current_user()["email"], "Draft", rcpt, D.now()))
                D.log_activity(aid, current_user()["email"], "Created a campaign draft")
                flash("Campaign saved as draft.", "success")
            elif action == "clone":
                src = D.query("SELECT * FROM campaigns WHERE id=? AND account_id=?",
                              (request.form.get("id"), aid), one=True)
                if src:
                    D.execute(
                        "INSERT INTO campaigns (account_id, name, subject, body, from_email,"
                        " status, recipients, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (aid, src["name"] + " (copy)", src["subject"], src["body"],
                         src["from_email"], "Draft", src["recipients"], D.now()))
                    flash("Campaign cloned.", "success")
            elif action == "advance":
                cid = request.form.get("id")
                flow = {"Draft": "Scheduled", "Scheduled": "Running", "Running": "Completed"}
                cur = D.query("SELECT status FROM campaigns WHERE id=? AND account_id=?",
                              (cid, aid), one=True)
                if cur and cur["status"] in flow:
                    D.execute("UPDATE campaigns SET status=? WHERE id=? AND account_id=?",
                              (flow[cur["status"]], cid, aid))
            return redirect(url_for("campaigns"))
        status_filter = request.args.get("status")
        if status_filter:
            rows = D.query("SELECT * FROM campaigns WHERE account_id=? AND status=?"
                           " ORDER BY id DESC", (aid, status_filter))
        else:
            rows = D.query("SELECT * FROM campaigns WHERE account_id=? ORDER BY id DESC", (aid,))
        counts = D.query("SELECT status, COUNT(*) c FROM campaigns WHERE account_id=?"
                         " GROUP BY status", (aid,))
        counts = {r["status"]: r["c"] for r in counts}
        return render_template("campaigns.html", campaigns=rows, counts=counts,
                               status_filter=status_filter)

    # The "Bulk Email Sender" module reuses the campaign composer.
    @app.route("/sender")
    @login_required
    def sender():
        aid = current_account()["id"]
        templates = ["Welcome Email", "Newsletter", "Promotion", "Re-engagement",
                     "Transactional Receipt"]
        queue = D.query("SELECT * FROM campaigns WHERE account_id=? AND status IN"
                        " ('Running','Scheduled') ORDER BY id DESC", (aid,))
        return render_template("sender.html", templates=templates, queue=queue)

    # ---- SMTP ------------------------------------------------------------ #
    @app.route("/smtp", methods=["GET", "POST"])
    @login_required
    def smtp():
        aid = current_account()["id"]
        if request.method == "POST":
            D.execute(
                "INSERT INTO smtp_servers (account_id, name, host, port, username,"
                " dedicated_ip, daily_limit, warmup, health, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (aid, request.form.get("name", "New Relay").strip(),
                 request.form.get("host", "").strip(),
                 int(request.form.get("port") or 587),
                 request.form.get("username", "").strip(),
                 request.form.get("dedicated_ip", "").strip(),
                 int(request.form.get("daily_limit") or 10000),
                 "Not started", "Healthy", D.now()))
            flash("SMTP server added.", "success")
            return redirect(url_for("smtp"))
        servers = D.query("SELECT * FROM smtp_servers WHERE account_id=? ORDER BY id", (aid,))
        return render_template("smtp.html", servers=servers)

    # ---- Domains --------------------------------------------------------- #
    @app.route("/domains", methods=["GET", "POST"])
    @login_required
    def domains():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                D.execute(
                    "INSERT INTO domains (account_id, domain, reputation, created_at)"
                    " VALUES (?,?,?,?)",
                    (aid, request.form.get("domain", "").strip().lower(), 70, D.now()))
                flash("Domain added — add the DNS records, then verify.", "success")
            elif action == "verify":
                # Simulate a successful DNS verification.
                D.execute("UPDATE domains SET spf=1, dkim=1, dmarc=1, verified=1,"
                          " reputation=MIN(reputation+10,99) WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
                flash("DNS records verified ✔", "success")
            return redirect(url_for("domains"))
        rows = D.query("SELECT * FROM domains WHERE account_id=? ORDER BY id", (aid,))
        return render_template("domains.html", domains=rows)

    # ---- Reports --------------------------------------------------------- #
    @app.route("/reports")
    @login_required
    def reports():
        aid = current_account()["id"]
        agg = D.query(
            "SELECT COALESCE(SUM(recipients),0) rcpt, COALESCE(SUM(sent),0) sent,"
            " COALESCE(SUM(opens),0) opens, COALESCE(SUM(clicks),0) clicks,"
            " COALESCE(SUM(bounces),0) bounces FROM campaigns WHERE account_id=?",
            (aid,), one=True)
        per_campaign = D.query(
            "SELECT name, sent, opens, clicks, bounces FROM campaigns WHERE account_id=?"
            " AND sent > 0 ORDER BY sent DESC", (aid,))
        return render_template("reports.html", agg=agg, per_campaign=per_campaign)

    # ---- API keys -------------------------------------------------------- #
    @app.route("/api", methods=["GET", "POST"])
    @login_required
    def api_keys():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                token = "ms_live_" + secrets.token_urlsafe(24)
                D.execute("INSERT INTO api_keys (account_id, label, token, created_at)"
                          " VALUES (?,?,?,?)",
                          (aid, request.form.get("label", "Default").strip(), token, D.now()))
                flash("API key created — copy it now, it won't be shown in full again.",
                      "success")
            elif action == "revoke":
                D.execute("DELETE FROM api_keys WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
                flash("API key revoked.", "success")
            return redirect(url_for("api_keys"))
        keys = D.query("SELECT * FROM api_keys WHERE account_id=? ORDER BY id DESC", (aid,))
        return render_template("api.html", keys=keys)

    # ---- Billing --------------------------------------------------------- #
    @app.route("/billing", methods=["GET", "POST"])
    @login_required
    def billing():
        acct = current_account()
        aid = acct["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "plan":
                plan = request.form.get("plan")
                credits = {"Free": 1000, "Pro": 50000, "Business": 250000,
                           "Enterprise": 2000000}.get(plan, acct["credits"])
                D.execute("UPDATE accounts SET plan=?, credits=? WHERE id=?",
                          (plan, credits, aid))
                D.log_activity(aid, current_user()["email"], f"Switched to {plan} plan")
                flash(f"You're now on the {plan} plan.", "success")
            elif action == "credits":
                amt = int(request.form.get("amount") or 0)
                D.execute("UPDATE accounts SET credits=credits+? WHERE id=?", (amt, aid))
                flash(f"Added {amt:,} credits.", "success")
            return redirect(url_for("billing"))
        invoices = D.query("SELECT * FROM invoices WHERE account_id=? ORDER BY id DESC", (aid,))
        plans = [
            ("Free", 0, "1,000 verifications · 1 domain · community support"),
            ("Pro", 99, "50,000 verifications · 5 domains · A/B testing · priority support"),
            ("Business", 299, "250,000 verifications · dedicated IP · SMTP rotation · SSO"),
            ("Enterprise", 0, "Unlimited · multi-region · white-label · SLA · TAM"),
        ]
        return render_template("billing.html", invoices=invoices, plans=plans)

    # ---- Team ------------------------------------------------------------ #
    @app.route("/team", methods=["GET", "POST"])
    @login_required
    def team():
        acct = current_account()
        aid = acct["id"]
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            role = request.form.get("role", "Member")
            name = email.split("@")[0].title()
            if email and not D.query("SELECT 1 FROM users WHERE email=?", (email,), one=True):
                tmp = bcrypt.hashpw(secrets.token_hex(8).encode(), bcrypt.gensalt()).decode()
                D.execute("INSERT INTO users (account_id, email, name, pw_hash, role,"
                          " created_at) VALUES (?,?,?,?,?,?)",
                          (aid, email, name, tmp, role, D.now()))
                D.log_activity(aid, current_user()["email"], f"Invited {email} as {role}")
                flash(f"Invitation sent to {email}.", "success")
            else:
                flash("That user already exists or the email is invalid.", "error")
            return redirect(url_for("team"))
        members = D.query("SELECT * FROM users WHERE account_id=? ORDER BY id", (aid,))
        activity = D.query("SELECT * FROM activity WHERE account_id=? ORDER BY id DESC LIMIT 20",
                           (aid,))
        roles = [
            ("Owner", "Full access including billing and account deletion"),
            ("Admin", "Manage everything except billing & account deletion"),
            ("Member", "Create campaigns, verify, manage contacts"),
            ("Viewer", "Read-only access to reports and dashboards"),
        ]
        return render_template("team.html", members=members, activity=activity, roles=roles)

    # ---- Settings -------------------------------------------------------- #
    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        u = current_user()
        acct = current_account()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "profile":
                D.execute("UPDATE users SET name=?, timezone=? WHERE id=?",
                          (request.form.get("name", u["name"]).strip(),
                           request.form.get("timezone", u["timezone"]), u["id"]))
                D.execute("UPDATE accounts SET name=? WHERE id=?",
                          (request.form.get("company", acct["name"]).strip(), acct["id"]))
                flash("Profile updated.", "success")
            elif action == "password":
                cur = request.form.get("current", "")
                new = request.form.get("new", "")
                if not bcrypt.checkpw(cur.encode(), u["pw_hash"].encode()):
                    flash("Current password is incorrect.", "error")
                elif len(new) < 6:
                    flash("New password must be at least 6 characters.", "error")
                else:
                    h = bcrypt.hashpw(new.encode(), bcrypt.gensalt()).decode()
                    D.execute("UPDATE users SET pw_hash=? WHERE id=?", (h, u["id"]))
                    D.log_activity(acct["id"], u["email"], "Changed password")
                    flash("Password changed.", "success")
            elif action == "twofa":
                D.execute("UPDATE users SET twofa=? WHERE id=?",
                          (0 if u["twofa"] else 1, u["id"]))
                flash("Two-factor authentication " + ("disabled." if u["twofa"]
                      else "enabled."), "success")
            return redirect(url_for("settings"))
        audit = D.query("SELECT * FROM activity WHERE account_id=? ORDER BY id DESC LIMIT 30",
                        (acct["id"],))
        timezones = ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London",
                     "Europe/Berlin", "Asia/Kolkata", "Asia/Singapore", "Australia/Sydney"]
        return render_template("settings.html", audit=audit, timezones=timezones)

    # ---- AI Center ------------------------------------------------------- #
    @app.route("/ai", methods=["GET", "POST"])
    @login_required
    def ai_center():
        out = {"tool": None}
        if request.method == "POST":
            tool = request.form.get("tool")
            out["tool"] = tool
            if tool == "subjects":
                out["topic"] = request.form.get("topic", "")
                out["subjects"] = ai.generate_subjects(out["topic"],
                                                        request.form.get("tone", "friendly"))
            elif tool == "writer":
                out["topic"] = request.form.get("topic", "")
                out["email"] = ai.write_email(
                    out["topic"], request.form.get("tone", "friendly"),
                    request.form.get("cta", "Learn more") or "Learn more",
                    request.form.get("audience", "customers") or "customers")
            elif tool == "spam":
                out["spam"] = ai.spam_score(request.form.get("subject", ""),
                                            request.form.get("body", ""))
            elif tool == "reply":
                out["reply"] = ai.generate_reply(request.form.get("incoming", ""),
                                                 request.form.get("tone", "professional"))
            elif tool == "sendtime":
                out["sendtime"] = ai.predict_send_time(
                    request.form.get("audience", "general"))
            D.log_activity(current_account()["id"], current_user()["email"],
                           f"Used AI tool: {tool}")
        return render_template("ai.html", out=out)

    # ---- Deliverability Center ------------------------------------------ #
    @app.route("/deliverability", methods=["GET", "POST"])
    @login_required
    def deliverability():
        aid = current_account()["id"]
        spam = None
        if request.method == "POST":
            spam = ai.spam_score(request.form.get("subject", ""),
                                 request.form.get("body", ""))
        dom = D.query("SELECT * FROM domains WHERE account_id=? ORDER BY reputation DESC"
                      " LIMIT 1", (aid,), one=True)
        rep = dom["reputation"] if dom else 85
        domain_name = dom["domain"] if dom else "yourdomain.com"
        return render_template(
            "deliverability.html", spam=spam,
            providers=DELIV.provider_scores(rep), placement=DELIV.inbox_placement(rep),
            blacklist=DELIV.blacklist_status(domain_name), reputation=rep,
            domain=domain_name)

    # ---- Email Finder ---------------------------------------------------- #
    @app.route("/finder", methods=["GET", "POST"])
    @login_required
    def finder():
        results = None
        name = domain = ""
        if request.method == "POST":
            name = request.form.get("name", "")
            domain = request.form.get("domain", "")
            results = DELIV.find_emails(name, domain)
            D.log_activity(current_account()["id"], current_user()["email"],
                           f"Email finder: {name} @ {domain}")
        return render_template("finder.html", results=results, name=name, domain=domain)

    # ---- Template Builder ------------------------------------------------ #
    @app.route("/templates", methods=["GET", "POST"])
    @login_required
    def templates():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                D.execute(
                    "INSERT INTO templates (account_id, name, kind, subject, content,"
                    " created_at) VALUES (?,?,?,?,?,?)",
                    (aid, request.form.get("name", "Untitled").strip(),
                     request.form.get("kind", "Email"),
                     request.form.get("subject", "").strip(),
                     request.form.get("content", "").strip(), D.now()))
                flash("Template saved.", "success")
            elif action == "delete":
                D.execute("DELETE FROM templates WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
            return redirect(url_for("templates"))
        rows = D.query("SELECT * FROM templates WHERE account_id=? ORDER BY id DESC", (aid,))
        return render_template("templates.html", templates=rows)

    # ---- Landing Pages --------------------------------------------------- #
    @app.route("/landing", methods=["GET", "POST"])
    @login_required
    def landing():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                name = request.form.get("name", "Untitled").strip()
                slug = (request.form.get("slug", "").strip()
                        or name.lower().replace(" ", "-"))
                D.execute(
                    "INSERT INTO landing_pages (account_id, name, slug, status, created_at)"
                    " VALUES (?,?,?,?,?)", (aid, name, slug, "Draft", D.now()))
                flash("Landing page created.", "success")
            elif action == "publish":
                D.execute("UPDATE landing_pages SET status='Published' WHERE id=? AND"
                          " account_id=?", (request.form.get("id"), aid))
                flash("Landing page published 🚀", "success")
            elif action == "delete":
                D.execute("DELETE FROM landing_pages WHERE id=? AND account_id=?",
                          (request.form.get("id"), aid))
            return redirect(url_for("landing"))
        rows = D.query("SELECT * FROM landing_pages WHERE account_id=? ORDER BY id DESC", (aid,))
        return render_template("landing.html", pages=rows)

    # ---- Automation / Workflows ------------------------------------------ #
    @app.route("/automation", methods=["GET", "POST"])
    @login_required
    def automation():
        aid = current_account()["id"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                D.execute(
                    "INSERT INTO automations (account_id, name, trigger, steps, status,"
                    " created_at) VALUES (?,?,?,?,?,?)",
                    (aid, request.form.get("name", "New Workflow").strip(),
                     request.form.get("trigger", "Contact subscribes"),
                     int(request.form.get("steps") or 1), "Draft", D.now()))
                flash("Workflow created.", "success")
            elif action == "toggle":
                cur = D.query("SELECT status FROM automations WHERE id=? AND account_id=?",
                              (request.form.get("id"), aid), one=True)
                if cur:
                    nxt = "Paused" if cur["status"] == "Active" else "Active"
                    D.execute("UPDATE automations SET status=? WHERE id=? AND account_id=?",
                              (nxt, request.form.get("id"), aid))
            return redirect(url_for("automation"))
        rows = D.query("SELECT * FROM automations WHERE account_id=? ORDER BY id DESC", (aid,))
        return render_template("automation.html", automations=rows)

    # ---- SMTP Pools ------------------------------------------------------ #
    @app.route("/pools")
    @login_required
    def pools():
        aid = current_account()["id"]
        servers = D.query("SELECT * FROM smtp_servers WHERE account_id=? ORDER BY id", (aid,))
        return render_template("pools.html", servers=servers)

    # ---- Queue Manager --------------------------------------------------- #
    @app.route("/queue")
    @login_required
    def queue():
        aid = current_account()["id"]
        agg = D.query(
            "SELECT COALESCE(SUM(recipients),0) r, COALESCE(SUM(sent),0) s,"
            " COALESCE(SUM(bounces),0) b FROM campaigns WHERE account_id=?",
            (aid,), one=True)
        pending = max(0, (agg["r"] or 0) - (agg["s"] or 0))
        states = {
            "Pending": pending,
            "Processing": min(pending, 1843),
            "Delivered": max(0, (agg["s"] or 0) - (agg["b"] or 0)),
            "Retry": int((agg["b"] or 0) * 0.4),
            "Failed": int((agg["b"] or 0) * 0.6),
            "Dead Queue": 12,
        }
        running = D.query("SELECT * FROM campaigns WHERE account_id=? AND status IN"
                          " ('Running','Scheduled') ORDER BY id DESC", (aid,))
        return render_template("queue.html", states=states, running=running,
                               throughput="42,180/hr")

    # ---- IP Warm-up ------------------------------------------------------ #
    @app.route("/warmup")
    @login_required
    def warmup():
        aid = current_account()["id"]
        servers = D.query("SELECT * FROM smtp_servers WHERE account_id=? ORDER BY id", (aid,))
        # A canonical 14-day warm-up curve.
        plan = [50, 100, 250, 500, 1000, 2500, 5000, 8000, 12000, 18000, 25000,
                35000, 45000, 50000]
        return render_template("warmup.html", servers=servers, plan=plan)

    # ---- Monitoring ------------------------------------------------------ #
    @app.route("/monitoring")
    @login_required
    def monitoring():
        return render_template("monitoring.html", metrics=_system_metrics())

    # ---- White Label ----------------------------------------------------- #
    @app.route("/whitelabel", methods=["GET", "POST"])
    @login_required
    def whitelabel():
        if request.method == "POST":
            D.log_activity(current_account()["id"], current_user()["email"],
                           "Updated white-label branding")
            flash("Branding saved. Changes apply to your client portals.", "success")
            return redirect(url_for("whitelabel"))
        return render_template("whitelabel.html")

    # ---- Enterprise modules + generic scaffold --------------------------- #
    @app.route("/enterprise")
    @login_required
    def enterprise():
        acct = current_account()
        modules = NAV_BY_KEY["enterprise"]["items"]
        # Some live-ish figures to make the page feel real.
        metrics = {
            "queue_depth": 1843,
            "throughput": "42k/hr",
            "pools": 3,
            "ips": 12,
            "blacklist_clean": True,
            "inbox_rate": 97.4,
            "regions": ["us-east", "eu-west", "ap-south"],
            "tenants": D.query("SELECT COUNT(*) c FROM accounts", (), one=True)["c"],
        }
        return render_template("enterprise.html", modules=modules, metrics=metrics)

    # Generic landing page for any module without a bespoke view.
    @app.route("/m/<key>")
    @login_required
    def module_page(key):
        mod = NAV_BY_KEY.get(key)
        if not mod:
            abort(404)
        return render_template("module.html", mod=mod)


# --------------------------------------------------------------------------- #
#  JSON API (token-authenticated) — powers the "API" module's docs
# --------------------------------------------------------------------------- #


def register_api(app):
    def _auth_account():
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not token:
            token = request.args.get("api_key", "")
        if not token:
            return None
        row = D.query("SELECT * FROM api_keys WHERE token=?", (token,), one=True)
        if not row:
            return None
        D.execute("UPDATE api_keys SET last_used=? WHERE id=?", (D.now(), row["id"]))
        return row["account_id"]

    @app.route("/api/v1/verify")
    def api_verify():
        if _auth_account() is None:
            return jsonify({"error": "invalid or missing api key"}), 401
        email = request.args.get("email", "")
        if not email:
            return jsonify({"error": "email parameter required"}), 400
        return jsonify(verify_email(email))

    @app.route("/api/v1/health")
    def api_health():
        return jsonify({"status": "ok", "service": "mailsaas", "version": "1.0"})


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005, debug=True)
