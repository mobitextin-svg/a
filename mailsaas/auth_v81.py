"""
auth_v81.py — ZyvoMail enterprise verification flow (additive module, v82)

Adds the modern SaaS post-signup verification experience:

  signup → /verify        6-digit EMAIL OTP  (auto-focus boxes, paste,
                          auto-submit, 10-min expiry, 60 s resend cooldown,
                          max 5 attempts, max 3 resends, single-use,
                          previous codes invalidated on resend)
        → /verify/mobile  optional MOBILE number + 6-digit SMS OTP
                          (5-min expiry, same attempt/resend policy,
                          Indian +91 validation, uniqueness check, skippable)
        → /welcome        guided setup wizard (existing onboarding_v73)

The classic /verify-email/<token> link still works — the OTP is an
additional, faster path. Fully additive: own migrations, no changes to
existing routes. All events are written to the activity log.

SMS delivery: set MAILSAAS_SMS_WEBHOOK to an HTTP endpoint that accepts
POST JSON {"to": "+91XXXXXXXXXX", "message": "..."} (e.g. an MSG91/Twilio
relay). Without it, codes are logged to the server console (dev mode) the
same way transactional email falls back.
"""

import os
import re
import json
import secrets
from datetime import datetime, timedelta

from flask import (request, session, redirect, url_for, render_template,
                   jsonify)

try:
    from . import db as D          # package layout (python -m mailsaas.run)
except ImportError:                 # flat layout (python run.py from folder)
    import db as D


# --------------------------------------------------------------------------- #
#  Policy (mirrors the enterprise security spec)
# --------------------------------------------------------------------------- #

EMAIL_OTP_TTL_MIN = 10     # "Code expires in 10 minutes"
MOBILE_OTP_TTL_MIN = 5     # "Six-digit OTP expires after 5 minutes"
OTP_MAX_ATTEMPTS = 5       # "Maximum 5 OTP verification attempts"
OTP_MAX_RESENDS = 3        # "Maximum 3 OTP resend requests"
RESEND_COOLDOWN_S = 60     # "60-second resend countdown"
RESEND_WINDOW_MIN = 60     # resend counter relaxes after an hour


_MIGRATIONS = [
    ("users", "email_otp",            "TEXT"),
    ("users", "email_otp_expires",    "TEXT"),
    ("users", "email_otp_attempts",   "INTEGER NOT NULL DEFAULT 0"),
    ("users", "email_otp_resends",    "INTEGER NOT NULL DEFAULT 0"),
    ("users", "email_otp_sent_at",    "TEXT"),
    ("users", "mobile",               "TEXT"),
    ("users", "mobile_verified",      "INTEGER NOT NULL DEFAULT 0"),
    ("users", "mobile_otp",           "TEXT"),
    ("users", "mobile_otp_expires",   "TEXT"),
    ("users", "mobile_otp_attempts",  "INTEGER NOT NULL DEFAULT 0"),
    ("users", "mobile_otp_resends",   "INTEGER NOT NULL DEFAULT 0"),
    ("users", "mobile_otp_sent_at",   "TEXT"),
]


def _migrate():
    dbc = D.get_db()
    for table, col, decl in _MIGRATIONS:
        cols = [r["name"] for r in dbc.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            dbc.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    dbc.commit()


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _gen_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _ts(dt=None):
    return (dt or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def _parse_ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:  # noqa: BLE001
        return None


def _mask_email(email):
    """kannan@gmail.com → k•••••n@gmail.com (never expose the full box name)."""
    try:
        name, dom = email.split("@", 1)
    except ValueError:
        return email
    if len(name) <= 2:
        return name[:1] + "•••@" + dom
    return name[0] + "•" * min(6, len(name) - 2) + name[-1] + "@" + dom


def _mask_mobile(msisdn):
    """+919876543210 → +91 ••••••3210."""
    if not msisdn:
        return ""
    digits = re.sub(r"\D", "", msisdn)
    tail = digits[-4:]
    cc = "+91 " if msisdn.startswith("+91") else ("+" + digits[:-10] + " "
                                                  if len(digits) > 10 else "")
    return f"{cc}••••••{tail}"


def _validate_mobile(raw):
    """Normalise to E.164. Indian numbers get strict validation (10 digits,
    first digit 6-9). Returns (ok, normalised_or_error_message)."""
    s = (raw or "").strip()
    if not s:
        return False, "Please enter your mobile number."
    digits = re.sub(r"[^\d+]", "", s)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    # Bare digit input → assume India (product is India-first).
    if digits.isdigit():
        if len(digits) < 10:
            return False, "Mobile number is too short."
        if len(digits) > 10:
            return False, "Mobile number is too long."
        digits = "+91" + digits
    if not digits.startswith("+"):
        return False, "Please enter a valid mobile number."
    body = digits[1:]
    if not body.isdigit():
        return False, "Please enter a valid mobile number."
    if digits.startswith("+91"):
        nat = digits[3:]
        if len(nat) < 10:
            return False, "Mobile number is too short."
        if len(nat) > 10:
            return False, "Mobile number is too long."
        if nat[0] not in "6789":
            return False, "Please enter a valid mobile number."
        return True, "+91" + nat
    # Other countries: E.164 length sanity (8–15 digits incl. country code).
    if len(body) < 8:
        return False, "Mobile number is too short."
    if len(body) > 15:
        return False, "Mobile number is too long."
    return True, digits


def _deliver_sms(to, message):
    """Send via the configured webhook relay; otherwise dev-log to console
    (never echoed to the browser in production)."""
    hook = os.environ.get("MAILSAAS_SMS_WEBHOOK")
    if hook:
        try:
            from urllib import request as _rq
            data = json.dumps({"to": to, "message": message}).encode()
            req = _rq.Request(hook, data=data,
                              headers={"Content-Type": "application/json"})
            _rq.urlopen(req, timeout=10)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[sms] webhook failed: {type(e).__name__}: {e}", flush=True)
            return False
    print(f"\n[DEV SMS] to={to}\n  {message}\n", flush=True)
    return False


class _OtpChannel:
    """One policy engine for both channels — only the column prefix, TTL and
    transport differ."""

    def __init__(self, prefix, ttl_min):
        self.p = prefix              # "email_otp" | "mobile_otp"
        self.ttl = ttl_min

    def state(self, u):
        exp = _parse_ts(u[self.p + "_expires"] or "")
        active = bool(u[self.p]) and exp and exp > datetime.utcnow()
        sent = _parse_ts(u[self.p + "_sent_at"] or "")
        cooldown = 0
        if sent:
            cd = RESEND_COOLDOWN_S - int((datetime.utcnow() - sent).total_seconds())
            cooldown = max(0, cd)
        return {"active": active, "expires": exp, "cooldown": cooldown,
                "attempts": u[self.p + "_attempts"] or 0,
                "resends": u[self.p + "_resends"] or 0, "sent": sent}

    def issue(self, uid, u):
        """Generate + persist a fresh code (invalidates any previous one).
        Returns (ok, code_or_error)."""
        st = self.state(u)
        if st["cooldown"] > 0:
            return False, {"msg": "Please wait before requesting another code.",
                           "cooldown": st["cooldown"]}
        # Resend budget relaxes after an hour of inactivity.
        resends = st["resends"]
        if st["sent"] and datetime.utcnow() - st["sent"] > timedelta(
                minutes=RESEND_WINDOW_MIN):
            resends = 0
        if resends >= OTP_MAX_RESENDS:
            return False, {"msg": "Too many codes requested. Please try again "
                                  "in an hour.", "cooldown": 0}
        code = _gen_otp()
        exp = _ts(datetime.utcnow() + timedelta(minutes=self.ttl))
        D.execute(f"UPDATE users SET {self.p}=?, {self.p}_expires=?,"
                  f" {self.p}_attempts=0, {self.p}_resends=?,"
                  f" {self.p}_sent_at=? WHERE id=?",
                  (code, exp, resends + 1, _ts(), uid))
        return True, code

    def check(self, uid, u, code):
        """Verify a submitted code. Returns (ok, error_message)."""
        code = re.sub(r"\D", "", code or "")
        if not code:
            return False, "Please enter the verification code."
        st = self.state(u)
        if not u[self.p]:
            return False, "This verification code has already been used."
        if st["attempts"] >= OTP_MAX_ATTEMPTS:
            return False, ("Too many incorrect attempts. "
                           "Please request a new verification code.")
        if not st["active"]:
            return False, "Your verification code has expired."
        if not secrets.compare_digest(code, u[self.p]):
            D.execute(f"UPDATE users SET {self.p}_attempts={self.p}_attempts+1"
                      " WHERE id=?", (uid,))
            left = OTP_MAX_ATTEMPTS - st["attempts"] - 1
            if left <= 0:
                return False, ("Too many incorrect attempts. "
                               "Please request a new verification code.")
            return False, "The verification code you entered is incorrect."
        # Single-use: clear immediately on success.
        D.execute(f"UPDATE users SET {self.p}=NULL, {self.p}_expires=NULL,"
                  f" {self.p}_attempts=0 WHERE id=?", (uid,))
        return True, ""


EMAIL_CH = _OtpChannel("email_otp", EMAIL_OTP_TTL_MIN)
MOBILE_CH = _OtpChannel("mobile_otp", MOBILE_OTP_TTL_MIN)


# --------------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------------- #

def register_auth_v81(app, current_user, current_account, deliver_email,
                      dev_mode=True):
    with app.app_context():
        try:
            _migrate()
        except Exception:
            pass

    def _fresh(uid):
        return D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)

    def _next_after_email(u):
        if not u["mobile_verified"]:
            return url_for("verify_mobile_page")
        acct = current_account()
        if acct and not acct["ob_done"]:
            return url_for("ob_welcome")
        return url_for("dashboard")

    # ---------------- email OTP ---------------- #

    @app.route("/verify")
    def verify_page():
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        if u["verified"]:
            return redirect(_next_after_email(u))
        return render_template("welcome_success.html", u=u,
                               masked_email=_mask_email(u["email"]),
                               ttl_min=EMAIL_OTP_TTL_MIN)

    @app.route("/verify/send", methods=["POST"])
    def verify_send():
        u = current_user()
        if not u:
            return jsonify(ok=False, msg="Please sign in again."), 401
        if u["verified"]:
            return jsonify(ok=True, verified=True, next=_next_after_email(u))
        body = request.get_json(silent=True) or {}
        st = EMAIL_CH.state(u)
        # Page-load auto-send: reuse an active code instead of burning resends.
        if body.get("auto") and st["active"]:
            return jsonify(ok=True, sent=False, cooldown=st["cooldown"],
                           masked=_mask_email(u["email"]))
        ok, res = EMAIL_CH.issue(u["id"], u)
        if not ok:
            return jsonify(ok=False, **res), 429
        code = res
        link = url_for("verify_email", token=u["verify_token"],
                       _external=True) if u["verify_token"] else ""
        sent = deliver_email(
            u["email"], "Your ZyvoMail verification code",
            f"Hi {u['name']},\n\nYour ZyvoMail verification code is: {code}\n"
            f"It expires in {EMAIL_OTP_TTL_MIN} minutes.\n\n"
            + (f"Prefer one click? Verify here: {link}\n\n" if link else "")
            + "If you didn't create this account, you can ignore this email.")
        D.log_activity(u["account_id"], u["email"],
                       "Email verification code sent")
        resp = {"ok": True, "sent": True, "cooldown": RESEND_COOLDOWN_S,
                "masked": _mask_email(u["email"])}
        if dev_mode and not sent:
            resp["dev_code"] = code           # dev builds only — no SMTP wired
        return jsonify(resp)

    @app.route("/verify/code", methods=["POST"])
    def verify_code():
        u = current_user()
        if not u:
            return jsonify(ok=False, msg="Please sign in again."), 401
        if u["verified"]:
            return jsonify(ok=True, next=_next_after_email(u))
        body = request.get_json(silent=True) or {}
        ok, err = EMAIL_CH.check(u["id"], u, body.get("code", ""))
        if not ok:
            D.log_activity(u["account_id"], u["email"],
                           "Email verification code rejected")
            return jsonify(ok=False, msg=err)
        D.execute("UPDATE users SET verified=1, verify_token=NULL WHERE id=?",
                  (u["id"],))
        D.log_activity(u["account_id"], u["email"],
                       "Verified email address (OTP)")
        return jsonify(ok=True, next=_next_after_email(_fresh(u["id"])))

    # ---------------- mobile number + OTP ---------------- #

    @app.route("/verify/mobile")
    def verify_mobile_page():
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        if not u["verified"]:
            return redirect(url_for("verify_page"))
        if u["mobile_verified"]:
            return redirect(_next_after_email(u))
        acct = current_account()
        prefill = (u["mobile"] or (acct["ob_mobile"] if acct else "") or "")
        return render_template("verify_mobile.html", u=u, prefill=prefill,
                               ttl_min=MOBILE_OTP_TTL_MIN)

    @app.route("/verify/mobile/send", methods=["POST"])
    def verify_mobile_send():
        u = current_user()
        if not u:
            return jsonify(ok=False, msg="Please sign in again."), 401
        body = request.get_json(silent=True) or {}
        ok, res = _validate_mobile(body.get("mobile", ""))
        if not ok:
            return jsonify(ok=False, msg=res)
        msisdn = res
        dup = D.query("SELECT 1 FROM users WHERE mobile=? AND"
                      " mobile_verified=1 AND id<>?", (msisdn, u["id"]),
                      one=True)
        if dup:
            return jsonify(ok=False, msg="This mobile number is already "
                                         "associated with another account.")
        D.execute("UPDATE users SET mobile=? WHERE id=?", (msisdn, u["id"]))
        u = _fresh(u["id"])
        ok, res2 = MOBILE_CH.issue(u["id"], u)
        if not ok:
            return jsonify(ok=False, **res2), 429
        code = res2
        sent = _deliver_sms(msisdn, f"{code} is your ZyvoMail verification "
                                    f"code. Valid for {MOBILE_OTP_TTL_MIN} "
                                    "minutes. Do not share it with anyone.")
        D.log_activity(u["account_id"], u["email"],
                       f"Mobile verification code sent to {_mask_mobile(msisdn)}")
        resp = {"ok": True, "cooldown": RESEND_COOLDOWN_S,
                "masked": _mask_mobile(msisdn)}
        if dev_mode and not sent:
            resp["dev_code"] = code
        return jsonify(resp)

    @app.route("/verify/mobile/code", methods=["POST"])
    def verify_mobile_code():
        u = current_user()
        if not u:
            return jsonify(ok=False, msg="Please sign in again."), 401
        if u["mobile_verified"]:
            return jsonify(ok=True, next=_next_after_email(u))
        body = request.get_json(silent=True) or {}
        ok, err = MOBILE_CH.check(u["id"], u, body.get("code", ""))
        if not ok:
            D.log_activity(u["account_id"], u["email"],
                           "Mobile verification code rejected")
            return jsonify(ok=False, msg=err)
        D.execute("UPDATE users SET mobile_verified=1 WHERE id=?", (u["id"],))
        D.log_activity(u["account_id"], u["email"],
                       "Verified mobile number " + _mask_mobile(u["mobile"]))
        return jsonify(ok=True, next=_next_after_email(_fresh(u["id"])))

    @app.route("/verify/mobile/skip", methods=["POST"])
    def verify_mobile_skip():
        u = current_user()
        if not u:
            return jsonify(ok=False), 401
        D.log_activity(u["account_id"], u["email"],
                       "Skipped mobile verification")
        acct = current_account()
        nxt = url_for("ob_welcome") if (acct and not acct["ob_done"]) \
            else url_for("dashboard")
        return jsonify(ok=True, next=nxt)
