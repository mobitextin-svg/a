import os
import sys
import uuid
import json
import secrets
import random
import shutil
import zipfile
import tempfile
import io
import base64
from datetime import datetime, timedelta
from pathlib import Path

# ── Dependency check — gives a clear message instead of a cryptic ImportError ─
_MISSING = []
try:
    from flask import (Flask, request, send_file, render_template,
                       abort, jsonify, redirect, url_for, session, flash)
except ImportError:
    _MISSING.append("flask")
try:
    import bcrypt
except ImportError:
    _MISSING.append("bcrypt")
try:
    from filelock import FileLock
except ImportError:
    _MISSING.append("filelock")
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    _MISSING.append("flask-limiter")

if _MISSING:
    print("\n" + "="*55)
    print("  ERROR: Missing required packages:")
    for pkg in _MISSING:
        print(f"    - {pkg}")
    print()
    print("  Fix: run this command, then restart:")
    print(f"    pip install {' '.join(_MISSING)}")
    print("="*55 + "\n")
    sys.exit(1)

try:
    import pyotp
    import qrcode
    TOTP_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
app.jinja_env.filters['enumerate'] = enumerate
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10 GB max upload

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# ── Auto-detect Cloudflare tunnel URL ────────────────────────────────────────
TUNNEL_URL_FILE = Path("current_tunnel_url.txt")

def get_tunnel_url():
    try:
        if TUNNEL_URL_FILE.exists():
            url = TUNNEL_URL_FILE.read_text().strip()
            if url:
                return url.rstrip("/")
    except:
        pass
    return None

def get_base_url(req):
    tunnel = get_tunnel_url()
    if tunnel:
        return tunnel + "/"
    return req.host_url

@app.after_request
def skip_ngrok_warning(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ── DB / Config paths ─────────────────────────────────────────────────────────
LINKS_DB      = Path("links.json")
REQS_DB       = Path("requests.json")
CONFIG_FILE   = Path("config.json")
RECOVERY_FILE = Path("recovery.json")
SHORTS_DB     = Path("shorts.json")
HISTORY_DB    = Path("download_history.json")   # NEW: download history log
CATEGORIES_DB = Path("categories.json")          # category list

UPLOAD_DIR    = Path("uploaded_files")
UPLOAD_DIR.mkdir(exist_ok=True)

CHUNK_DIR     = Path("chunk_tmp")
CHUNK_DIR.mkdir(exist_ok=True)

SHORT_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
SHORT_LEN = 5

ALLOWED_EXTENSIONS = None   # None = allow all; or set({'pdf','png','zip',...})

# ── Helpers ───────────────────────────────────────────────────────────────────
def _lock_for(path: Path) -> FileLock:
    """Return a FileLock for the given JSON path (lock file sits beside it)."""
    return FileLock(str(path) + ".lock", timeout=10)

def load_json(path):
    p = Path(path)
    with _lock_for(p):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}

def save_json(path, data):
    p = Path(path)
    with _lock_for(p):
        # Atomic write: write to temp file then rename to avoid partial writes
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(p)

# ── Password hashing (bcrypt) ─────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    """Hash a password with bcrypt (returns a str for JSON storage)."""
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def check_pw(pw: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(pw.encode(), stored_hash.encode())
    except Exception:
        return False

def get_config():   return load_json(CONFIG_FILE)
def save_config(c): save_json(CONFIG_FILE, c)

# ── Persistent secret_key ─────────────────────────────────────────────────────
def _load_or_create_secret_key() -> str:
    cfg = load_json(CONFIG_FILE)
    key = cfg.get("secret_key")
    if not key:
        key = secrets.token_hex(32)
        cfg["secret_key"] = key
        save_json(CONFIG_FILE, cfg)
    return key

app.secret_key = _load_or_create_secret_key()

# ── TOTP / 2FA helpers ────────────────────────────────────────────────────────
def get_totp_secret():
    return get_config().get("totp_secret")

def is_2fa_enabled():
    return bool(get_totp_secret()) and TOTP_AVAILABLE

def verify_totp(code: str) -> bool:
    secret = get_totp_secret()
    if not secret or not TOTP_AVAILABLE:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def generate_totp_qr(secret: str, issuer: str = "FileShare") -> str:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name="Admin", issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def is_setup_done(): return bool(get_config().get("password_hash"))
def check_admin(pw): return check_pw(pw, get_config().get("password_hash", ""))
def is_logged_in():  return session.get("admin_logged_in") is True

def make_short_code():
    shorts = load_json(SHORTS_DB)
    for _ in range(100):
        code = "".join(random.choices(SHORT_ALPHABET, k=SHORT_LEN))
        if code not in shorts:
            return code
    return "".join(random.choices(SHORT_ALPHABET, k=7))

def days_left(expires_at_str):
    try:
        exp = datetime.fromisoformat(expires_at_str)
        return (exp - datetime.utcnow()).days
    except:
        return -999

def auto_delete_expired_links(grace_days: int):
    """Delete links (and their files) that expired more than grace_days ago.
    grace_days=0  → delete as soon as expired (immediately)
    grace_days>0  → delete after N days past expiry
    grace_days<0  → disabled
    """
    if grace_days < 0:
        return 0  # disabled
    links  = load_json(LINKS_DB)
    shorts = load_json(SHORTS_DB)
    # grace_days=0: cutoff == now, so anything past expiry is deleted immediately
    cutoff = datetime.utcnow() - timedelta(days=grace_days)
    to_del = []
    for tok, entry in links.items():
        try:
            exp = datetime.fromisoformat(entry.get("expires_at", ""))
            if exp < cutoff:
                to_del.append(tok)
        except:
            pass
    if not to_del:
        return 0
    for tok in to_del:
        entry = links[tok]
        fp = Path(entry.get("file_path", ""))
        try:
            if fp.is_file():
                fp.unlink()
            if fp.parent.exists() and not any(fp.parent.iterdir()):
                fp.parent.rmdir()
        except Exception:
            pass
        code = entry.get("short_code")
        if code:
            shorts.pop(code, None)
        del links[tok]
    save_json(LINKS_DB, links)
    save_json(SHORTS_DB, shorts)
    return len(to_del)

def get_categories():
    data = load_json(CATEGORIES_DB)
    return data.get("categories", [])

def save_categories(cats):
    save_json(CATEGORIES_DB, {"categories": cats})

def get_mobile_for_download(token: str, device_id: str, mobile: str) -> str:
    """
    Return the best mobile number for a download log entry.
    Priority: form-submitted value → requests.json (token+fingerprint) → requests.json (token only) → '—'
    """
    if mobile and mobile.strip() and mobile.strip() != "—":
        return mobile.strip()
    # Look up from requests.json — first try exact token+fingerprint match
    reqs = load_json(REQS_DB)
    token_only_candidate = None
    for r in reqs.values():
        if r.get("token") != token:
            continue
        found = r.get("phone") or r.get("mobile") or ""
        if found and found.strip() and "@" not in found:
            if r.get("fingerprint") == device_id:
                return found.strip()   # exact match — return immediately
            token_only_candidate = found.strip()  # save as fallback
    if token_only_candidate:
        return token_only_candidate
    return "—"

def log_download(mobile: str, filename: str, device_id: str, token: str):
    """Append one row to download_history.json."""
    history = load_json(HISTORY_DB)
    row_id = uuid.uuid4().hex[:8].upper()
    resolved_mobile = get_mobile_for_download(token, device_id, mobile)
    history[row_id] = {
        "mobile":        resolved_mobile,
        "filename":      filename,
        "device_id":     device_id,
        "token":         token,
        "downloaded_at": datetime.utcnow().isoformat(),
    }
    save_json(HISTORY_DB, history)

# ── SETUP ─────────────────────────────────────────────────────────────────────
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if is_setup_done(): return redirect(url_for("admin"))
    error = None
    if request.method == "POST":
        pw  = request.form.get("password", "")
        pw2 = request.form.get("confirm", "")
        rec = request.form.get("recovery_phrase", "").strip()
        if len(pw) < 6:    error = "Password must be at least 6 characters."
        elif pw != pw2:    error = "Passwords do not match."
        elif len(rec) < 4: error = "Recovery phrase must be at least 4 characters."
        else:
            cfg = get_config()
            cfg["password_hash"] = hash_pw(pw)
            save_config(cfg)
            # Store only a bcrypt hash of the recovery phrase — never plain text
            save_json(RECOVERY_FILE, {"recovery_hash": hash_pw(rec.lower())})
            session["admin_logged_in"] = True
            flash("✅ Password set! Welcome to FileShare Admin.", "success")
            return redirect(url_for("admin"))
    return render_template("setup.html", error=error)

# ── LOGIN / LOGOUT ────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if not is_setup_done(): return redirect(url_for("setup"))
    if is_logged_in():      return redirect(url_for("admin"))
    error = None
    step  = session.get("login_step", "password")   # "password" | "totp"

    if request.method == "POST":
        action = request.form.get("action", "password")

        if action == "password":
            if check_admin(request.form.get("password", "")):
                if is_2fa_enabled():
                    session["login_step"]         = "totp"
                    session["password_verified"]  = True
                    return render_template("login.html", step="totp", error=None)
                else:
                    session.pop("login_step", None)
                    session.pop("password_verified", None)
                    session["admin_logged_in"] = True
                    return redirect(url_for("admin"))
            error = "Incorrect password. Try again."
            session.pop("login_step", None)
            session.pop("password_verified", None)

        elif action == "totp":
            if not session.get("password_verified"):
                return redirect(url_for("login"))
            code = request.form.get("totp_code", "").strip().replace(" ", "")
            if verify_totp(code):
                session.pop("login_step", None)
                session.pop("password_verified", None)
                session["admin_logged_in"] = True
                return redirect(url_for("admin"))
            error = "Invalid authenticator code. Try again."
            return render_template("login.html", step="totp", error=error)

    step = session.get("login_step", "password")
    return render_template("login.html", step=step, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── SMTP / EMAIL HELPERS ──────────────────────────────────────────────────────
import smtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

OTP_FILE = Path("otp_store.json")

def get_smtp_config():
    return get_config().get("smtp", {})

def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP via configured SMTP. Returns True on success."""
    smtp = get_smtp_config()
    if not smtp.get("host") or not smtp.get("user") or not smtp.get("password"):
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "FileShare — Password Reset OTP"
        msg["From"]    = smtp.get("from_addr") or smtp["user"]
        msg["To"]      = to_email
        html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;background:#0d0f17;color:#e2e8f0;padding:32px;border-radius:12px">
  <h2 style="color:#38bdf8;margin:0 0 8px">FileShare — Password Reset</h2>
  <p style="color:#94a3b8;margin:0 0 24px">Your one-time OTP code:</p>
  <div style="background:#1e2232;border:1px solid #334155;border-radius:8px;padding:24px;text-align:center">
    <span style="font-size:36px;font-weight:700;letter-spacing:12px;color:#38bdf8">{otp}</span>
  </div>
  <p style="color:#64748b;font-size:13px;margin:20px 0 0">Expires in <b>10 minutes</b>. Do not share this code.</p>
</div>"""
        msg.attach(MIMEText(html_body, "html"))
        port = int(smtp.get("port", 587))
        use_ssl = smtp.get("use_ssl", False)
        if use_ssl:
            s = smtplib.SMTP_SSL(smtp["host"], port, timeout=10)
        else:
            s = smtplib.SMTP(smtp["host"], port, timeout=10)
            s.starttls()
        s.login(smtp["user"], smtp["password"])
        s.sendmail(msg["From"], [to_email], msg.as_string())
        s.quit()
        return True
    except Exception as e:
        app.logger.error(f"SMTP error: {e}")
        return False

def generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)  # 6-digit

def save_otp(email: str, otp: str):
    data = {
        "email":      email.lower().strip(),
        "otp_hash":   hashlib.sha256(otp.encode()).hexdigest(),
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        "used":       False,
    }
    save_json(OTP_FILE, data)

def verify_otp(email: str, otp: str) -> tuple[bool, str]:
    """Returns (ok, error_message)."""
    data = load_json(OTP_FILE)
    if not data:
        return False, "No OTP found. Please request a new one."
    if data.get("used"):
        return False, "OTP already used. Please request a new one."
    if data.get("email") != email.lower().strip():
        return False, "Email does not match. Please request a new OTP."
    try:
        if datetime.fromisoformat(data["expires_at"]) < datetime.utcnow():
            return False, "OTP has expired. Please request a new one."
    except Exception:
        return False, "Invalid OTP record."
    if data.get("otp_hash") != hashlib.sha256(otp.encode()).hexdigest():
        return False, "Incorrect OTP. Please try again."
    # Mark used
    data["used"] = True
    save_json(OTP_FILE, data)
    return True, ""

# ── FORGOT PASSWORD (Email OTP flow) ─────────────────────────────────────────
@app.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot():
    error   = None
    success = None
    step    = request.args.get("step", "email")   # email | otp | reset

    smtp_configured = bool(get_smtp_config().get("host"))
    recovery_email  = get_config().get("recovery_email", "")

    if request.method == "POST":
        action = request.form.get("action")

        # ── STEP 1: send OTP ──────────────────────────────────────────────────
        if action == "send_otp":
            entered = request.form.get("email", "").strip().lower()
            if not smtp_configured:
                error = "SMTP not configured. Ask your admin to set up email settings."
            elif not recovery_email:
                error = "No recovery email set. Ask admin to configure one."
            elif entered != recovery_email.lower().strip():
                error = "Email does not match the registered recovery email."
            else:
                otp = generate_otp()
                save_otp(entered, otp)
                if send_otp_email(entered, otp):
                    session["otp_email"] = entered
                    return redirect(url_for("forgot", step="otp"))
                else:
                    error = "Failed to send email. Check SMTP settings."

        # ── STEP 2: verify OTP ────────────────────────────────────────────────
        elif action == "verify_otp":
            otp_input = request.form.get("otp", "").strip().replace(" ", "")
            email     = session.get("otp_email", "")
            ok, msg   = verify_otp(email, otp_input)
            if ok:
                session["recovery_verified"] = True
                return redirect(url_for("forgot", step="reset"))
            error = msg
            step  = "otp"

        # ── STEP 3: reset password ────────────────────────────────────────────
        elif action == "reset_password":
            if not session.get("recovery_verified"):
                return redirect(url_for("forgot"))
            pw  = request.form.get("password", "")
            pw2 = request.form.get("confirm", "")
            if len(pw) < 6:   error = "Password must be at least 6 characters."
            elif pw != pw2:   error = "Passwords do not match."
            else:
                cfg = get_config()
                cfg["password_hash"] = hash_pw(pw)
                save_config(cfg)
                session.pop("recovery_verified", None)
                session.pop("otp_email", None)
                session["admin_logged_in"] = True
                flash("✅ Password reset successfully!", "success")
                return redirect(url_for("admin"))

    if step == "otp"   and not session.get("otp_email"):
        return redirect(url_for("forgot"))
    if step == "reset" and not session.get("recovery_verified"):
        return redirect(url_for("forgot"))

    masked_email = ""
    if recovery_email:
        parts = recovery_email.split("@")
        masked_email = parts[0][:2] + "****@" + parts[1] if len(parts) == 2 else "****"

    return render_template("forgot.html", error=error, success=success,
                           step=step, masked_email=masked_email,
                           smtp_configured=smtp_configured)

# ── SMTP SETTINGS (admin only) ────────────────────────────────────────────────
@app.route("/admin/smtp", methods=["GET", "POST"])
def smtp_settings():
    if not is_logged_in(): return redirect(url_for("login"))
    error   = None
    success = None
    cfg     = get_config()
    smtp    = cfg.get("smtp", {})

    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            smtp = {
                "host":      request.form.get("host", "").strip(),
                "port":      int(request.form.get("port", 587) or 587),
                "user":      request.form.get("user", "").strip(),
                "password":  request.form.get("password", "").strip(),
                "from_addr": request.form.get("from_addr", "").strip(),
                "use_ssl":   request.form.get("use_ssl") == "1",
            }
            cfg["smtp"]           = smtp
            cfg["recovery_email"] = request.form.get("recovery_email", "").strip().lower()
            save_config(cfg)
            success = "✅ SMTP settings saved."
        elif action == "test":
            to = cfg.get("recovery_email", smtp.get("user", ""))
            if to and send_otp_email(to, "123456"):
                success = f"✅ Test email sent to {to}."
            else:
                error = "❌ Test failed. Check SMTP settings and try again."

    return render_template("smtp_settings.html",
                           smtp=smtp,
                           recovery_email=cfg.get("recovery_email", ""),
                           error=error, success=success)

# ── CHANGE PASSWORD ───────────────────────────────────────────────────────────
@app.route("/change-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def change_password():
    if not is_setup_done(): return redirect(url_for("setup"))
    if not is_logged_in():  return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        if not check_admin(request.form.get("old_password", "")):
            error = "Current password is incorrect."
        elif len(request.form.get("password", "")) < 6:
            error = "New password must be at least 6 characters."
        elif request.form.get("password") != request.form.get("confirm"):
            error = "New passwords do not match."
        else:
            cfg = get_config()
            cfg["password_hash"] = hash_pw(request.form["password"])
            save_config(cfg)
            flash("✅ Password changed successfully!", "success")
            return redirect(url_for("admin"))
    return render_template("change_password.html", error=error)

# ── ROOT ──────────────────────────────────────────────────────────────────────
@app.route("/")
def root():
    if not is_setup_done(): return redirect(url_for("setup"))
    if not is_logged_in():  return redirect(url_for("login"))
    return redirect(url_for("admin"))

# ── SHORT LINK REDIRECT ───────────────────────────────────────────────────────
_CRAWLER_TOKENS = (
    "whatsapp", "google", "googlebot", "google-inspection",
    "telegrambot", "twitterbot", "facebookexternalhit",
    "applebot", "linkedinbot", "slackbot", "discordbot",
    "bot", "crawler", "spider", "preview", "fetch",
)

def _is_crawler(ua: str) -> bool:
    ua = ua.lower()
    return any(t in ua for t in _CRAWLER_TOKENS)

@app.route("/s/<code>")
def short_redirect(code):
    shorts = load_json(SHORTS_DB)
    token  = shorts.get(code)
    if not token:
        return render_template("expired.html", reason="Short link not found or expired."), 404

    ua = request.headers.get("User-Agent", "")
    if _is_crawler(ua):
        links  = load_json(LINKS_DB)
        entry  = links.get(token, {})
        label  = entry.get("label") or entry.get("filename", "File")
        base   = get_base_url(request).rstrip("/")
        dest   = f"{base}/download/{token}"
        thumb  = f"{base}/og-thumb/{token}.png"
        html = (
            "<!DOCTYPE html><html><head>\n"
            "<meta charset=\"UTF-8\">\n"
            f"<title>Download \u2014 {label}</title>\n"
            f'<meta property="og:title" content="Download \u2014 {label}">\n'
            '<meta property="og:description" content="Tap to securely download your file.">\n'
            f'<meta property="og:image" content="{thumb}">\n'
            '<meta property="og:image:width" content="1200">\n'
            '<meta property="og:image:height" content="630">\n'
            f'<meta property="og:url" content="{dest}">\n'
            '<meta property="og:type" content="website">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:title" content="Download \u2014 {label}">\n'
            '<meta name="twitter:description" content="Tap to securely download your file.">\n'
            f'<meta name="twitter:image" content="{thumb}">\n'
            f'<meta http-equiv="refresh" content="0;url={dest}">\n'
            f'</head><body><a href="{dest}">Click here to download</a></body></html>'
        )
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    return redirect(url_for("download_page", token=token))

# ── ADMIN DASHBOARD ───────────────────────────────────────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not is_setup_done(): return redirect(url_for("setup"))
    if not is_logged_in():  return redirect(url_for("login"))

    link_url  = None
    short_url = None
    links     = load_json(LINKS_DB)
    reqs      = load_json(REQS_DB)
    pending   = {k: v for k, v in reqs.items() if v.get("status") == "pending"}

    if request.method == "POST":
        action = request.form.get("action", "create")

        # ── CREATE LINK via UPLOAD ───────────────────────────────────────────
        if action == "create":
            days     = int(request.form.get("days", 30))
            uploaded = request.files.getlist("upload_files")
            uploaded = [f for f in uploaded if f and f.filename]

            if not uploaded:
                flash("❌ Please select at least one file to upload.", "error")
            else:
                # Multiple files → zip them together
                if len(uploaded) > 1:
                    zip_name  = request.form.get("zip_name", "").strip() or "files"
                    safe_zip  = "".join(c for c in zip_name if c.isalnum() or c in "._- ")
                    safe_zip  = safe_zip.strip() or "files"
                    file_uid  = uuid.uuid4().hex[:8]
                    dest_dir  = UPLOAD_DIR / file_uid
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    zip_path  = dest_dir / f"{safe_zip}.zip"
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in uploaded:
                            # Preserve relative folder structure if browser sends it
                            rel = f.filename.replace("\\", "/")
                            zf.writestr(rel, f.read())
                    save_path = zip_path
                    filename  = zip_path.name
                else:
                    f         = uploaded[0]
                    safe_name = Path(f.filename).name
                    file_uid  = uuid.uuid4().hex[:8]
                    dest_dir  = UPLOAD_DIR / file_uid
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    save_path = dest_dir / safe_name
                    f.save(str(save_path))
                    filename  = safe_name

                token      = uuid.uuid4().hex
                expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
                code       = make_short_code()
                shorts     = load_json(SHORTS_DB)
                shorts[code] = token
                save_json(SHORTS_DB, shorts)
                label_raw  = request.form.get("label", "").strip()
                links[token] = {
                    "file_path":   str(save_path),
                    "filename":    filename,
                    "label":       label_raw or filename,
                    "expires_at":  expires_at,
                    "locked_to":   [],
                    "created_at":  datetime.utcnow().isoformat(),
                    "request_id":  request.form.get("request_id") or None,
                    "short_code":  code,
                    "file_count":  len(uploaded),
                }
                save_json(LINKS_DB, links)
                rid = request.form.get("request_id")
                if rid and rid in reqs:
                    reqs[rid]["status"] = "fulfilled"
                    reqs[rid]["token"]  = token
                    save_json(REQS_DB, reqs)
                base      = get_base_url(request)
                link_url  = base + "download/" + token
                short_url = base + "s/" + code
                flash(f"✅ {'Zipped & link created' if len(uploaded)>1 else 'Uploaded & link created'}! Expires in {days} day(s).", "success")

        elif action == "revoke":
            tok = request.form.get("token")
            if tok in links:
                code = links[tok].get("short_code")
                if code:
                    shorts = load_json(SHORTS_DB)
                    shorts.pop(code, None)
                    save_json(SHORTS_DB, shorts)
                del links[tok]
                save_json(LINKS_DB, links)
                flash("🗑 Link revoked.", "info")

        elif action == "bulk_revoke":
            tokens  = request.form.getlist("tokens")
            removed = 0
            shorts  = load_json(SHORTS_DB)
            for tok in tokens:
                if tok in links:
                    code = links[tok].get("short_code")
                    if code: shorts.pop(code, None)
                    del links[tok]
                    removed += 1
            save_json(LINKS_DB, links)
            save_json(SHORTS_DB, shorts)
            flash(f"🗑 {removed} link(s) revoked.", "info")

        elif action == "approve_device":
            tok = request.form.get("token")
            fp  = request.form.get("fingerprint")
            rid = request.form.get("request_id")
            if tok in links and fp:
                locked = links[tok].get("locked_to", [])
                if isinstance(locked, str): locked = [locked]
                if fp not in locked:
                    locked.append(fp)
                links[tok]["locked_to"] = locked
                save_json(LINKS_DB, links)
            if rid and rid in reqs:
                reqs[rid]["status"] = "approved"
                save_json(REQS_DB, reqs)
            flash("✅ Device approved! They can now download.", "success")

        elif action == "reject_device":
            rid = request.form.get("request_id")
            if rid and rid in reqs:
                reqs[rid]["status"] = "rejected"
                save_json(REQS_DB, reqs)
            flash("❌ Request rejected.", "info")

        if short_url:
            return redirect(url_for("admin") + f"?link={link_url}&short={short_url}")
        return redirect(url_for("admin"))

    # ── GET ───────────────────────────────────────────────────────────────────
    link_url  = request.args.get("link")
    short_url = request.args.get("short")
    now       = datetime.utcnow().isoformat()[:10]
    shorts    = load_json(SHORTS_DB)

    # Auto-delete expired links per grace setting
    cfg_now         = get_config()
    expiry_grace    = int(cfg_now.get("expiry_grace_days", -1))  # -1 = disabled
    deleted_count   = auto_delete_expired_links(expiry_grace)
    if deleted_count:
        links = load_json(LINKS_DB)   # reload after cleanup
        flash(f"🗑 {deleted_count} expired link(s) auto-deleted.", "info")

    # Clean stale chunk_tmp dirs older than 24 h
    cutoff_ts = datetime.utcnow().timestamp() - 86400
    try:
        for d in CHUNK_DIR.iterdir():
            if d.is_dir() and d.stat().st_mtime < cutoff_ts:
                shutil.rmtree(str(d), ignore_errors=True)
    except Exception:
        pass

    pending_new    = {k: v for k, v in pending.items() if not v.get("token")}
    pending_device = {k: v for k, v in pending.items() if v.get("token")}

    short_map     = {}
    days_left_map = {}
    base          = get_base_url(request)
    for tok, l in links.items():
        code = l.get("short_code")
        if code and code in shorts:
            short_map[tok] = base + "s/" + code
        else:
            new_code = make_short_code()
            shorts[new_code] = tok
            links[tok]["short_code"] = new_code
            short_map[tok] = base + "s/" + new_code
        days_left_map[tok] = days_left(l.get("expires_at", ""))

    if any("short_code" not in l for l in links.values()):
        save_json(LINKS_DB, links)
        save_json(SHORTS_DB, shorts)

    slug_map = {}
    for _slug, _tok in load_json(SLUGS_DB).items():
        slug_map[_tok] = _slug

    return render_template("admin.html",
        now=now,
        link_url=link_url, short_url=short_url,
        links=links, short_map=short_map, days_left_map=days_left_map,
        slug_map=slug_map,
        pending_new=pending_new, pending_device=pending_device,
        total_links=len(links),
        download_count=len(load_json(HISTORY_DB)),
        active_links=sum(1 for l in links.values()
                         if l.get("expires_at", "")[:10] >= now),
        pending_count=len(pending),
        expiry_grace=expiry_grace,
        categories=get_categories())

# ── SAVE EXPIRY GRACE SETTING ─────────────────────────────────────────────────
@app.route("/admin/set-expiry-grace", methods=["POST"])
def set_expiry_grace():
    if not is_logged_in(): return redirect(url_for("login"))
    val = request.form.get("expiry_grace_days", "-1").strip()
    try:
        days = int(val)
    except ValueError:
        days = -1
    cfg = get_config()
    cfg["expiry_grace_days"] = days
    save_config(cfg)
    label = f"{days} day(s) after expiry" if days >= 0 else "disabled"
    flash(f"✅ Auto-delete set to: {label}.", "success")
    return redirect(url_for("admin"))

# ── DOWNLOAD HISTORY (admin view) ─────────────────────────────────────────────
@app.route("/admin/history")
def download_history():
    if not is_setup_done(): return redirect(url_for("setup"))
    if not is_logged_in():  return redirect(url_for("login"))
    history = load_json(HISTORY_DB)
    # Sort newest first
    rows = sorted(history.values(),
                  key=lambda r: r.get("downloaded_at", ""), reverse=True)
    return render_template("download_history.html", rows=rows)

# ── CLEAR HISTORY (admin action) ──────────────────────────────────────────────
@app.route("/admin/history/clear", methods=["POST"])
def clear_history():
    if not is_logged_in(): return redirect(url_for("login"))
    save_json(HISTORY_DB, {})
    flash("🗑 Download history cleared.", "info")
    return redirect(url_for("download_history"))

# ── DOWNLOAD PAGE ─────────────────────────────────────────────────────────────
@app.route("/download/<token>")
def download_page(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return render_template("expired.html", reason="Invalid or revoked link."), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return render_template("expired.html", reason="This link has expired."), 410
    label = entry.get("label") or entry["filename"]
    record_event(token, "view", request, request.args.get("fp", ""))
    return render_template("download.html", token=token, filename=entry["filename"],
                           label=label, kind=viewer_kind(entry),
                           share_url=share_url_for(token, request))

# ── DOWNLOAD VERIFY  (returns JSON — consumed by download.html XHR) ──────────
@app.route("/download/<token>/verify", methods=["POST"])
@limiter.limit("20 per minute")
def download_verify(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return jsonify({"error": "invalid"}), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return jsonify({"error": "expired"}), 410

    fingerprint = request.form.get("fingerprint", "")
    mobile      = request.form.get("mobile", "").strip()
    link_mode   = entry.get("mode", "locked")
    locked_to   = entry.get("locked_to", [])
    if isinstance(locked_to, str): locked_to = [locked_to]

    # ── LINK PASSWORD CHECK ───────────────────────────────────────────────────
    link_pw_hash = entry.get("link_password_hash")
    if link_pw_hash:
        submitted_pw = request.form.get("link_password", "").strip()
        if not check_pw(submitted_pw, link_pw_hash):
            return jsonify({"error": "wrong_password"}), 403

    # ── OPEN MODE ─────────────────────────────────────────────────────────────
    if link_mode == "open":
        session[f"dl_ok_{token}"] = fingerprint or "open"
        session[f"fp_{token}"]    = fingerprint
        return jsonify({"ok": True})

    # ── LOCKED: first device — auto-approve ──────────────────────────────────
    if not locked_to:
        entry["locked_to"] = [fingerprint]
        links[token] = entry
        save_json(LINKS_DB, links)
        session[f"dl_ok_{token}"] = fingerprint
        session[f"fp_{token}"]    = fingerprint
        return jsonify({"ok": True})

    # ── LOCKED: already-approved device ──────────────────────────────────────
    if fingerprint in locked_to:
        session[f"dl_ok_{token}"] = fingerprint
        session[f"fp_{token}"]    = fingerprint
        return jsonify({"ok": True})

    # ── LOCKED: new/unknown device — needs admin approval ────────────────────
    reqs = load_json(REQS_DB)
    already = any(
        r.get("token") == token and
        r.get("fingerprint") == fingerprint and
        r.get("status") == "pending"
        for r in reqs.values()
    )
    if not already:
        rid = uuid.uuid4().hex[:8].upper()
        reqs[rid] = {
            "name":        request.form.get("req_name", ""),
            "email":       request.form.get("req_email", ""),
            "mobile":      mobile,
            "filename":    entry["filename"],
            "token":       token,
            "fingerprint": fingerprint,
            "status":      "pending",
            "created_at":  datetime.utcnow().isoformat(),
        }
        save_json(REQS_DB, reqs)

    session[f"fp_{token}"]  = fingerprint
    session[f"mob_{token}"] = mobile

    if mobile:
        reqs2 = load_json(REQS_DB)
        for rid2, r2 in reqs2.items():
            if (r2.get("token") == token and
                    r2.get("fingerprint") == fingerprint and
                    r2.get("status") == "pending"):
                r2["phone"] = mobile
                reqs2[rid2] = r2
                break
        save_json(REQS_DB, reqs2)

    return jsonify({"pending": True,
                    "redirect": f"/download/{token}/pending",
                    "token": token, "fingerprint": fingerprint})

# ── DOWNLOAD STREAM  (actual file — Range-aware, progress-bar friendly) ──────
@app.route("/download/<token>/stream")
def download_stream(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return jsonify({"error": "invalid"}), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return jsonify({"error": "expired"}), 410

    ok_fp = session.get(f"dl_ok_{token}")
    if not ok_fp:
        return jsonify({"error": "not_verified"}), 403

    filepath = Path(entry.get("file_path", ""))
    if not filepath.is_file():
        return jsonify({"error": "file_missing"}), 404

    log_download(
        mobile    = session.get(f"mob_{token}", "—"),
        filename  = entry["filename"],
        device_id = ok_fp,
        token     = token,
    )
    record_event(token, "download", request, ok_fp)

    return send_file(str(filepath), as_attachment=True,
                     download_name=entry["filename"],
                     conditional=True)

# ── PENDING PAGE ──────────────────────────────────────────────────────────────
@app.route("/download/<token>/pending")
def download_pending(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return render_template("expired.html", reason="Invalid or revoked link."), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return render_template("expired.html", reason="This link has expired."), 410
    fingerprint   = session.get(f"fp_{token}", "")
    contact_saved = request.args.get("saved") == "1"
    locked_to     = entry.get("locked_to", [])
    if isinstance(locked_to, str): locked_to = [locked_to]
    if fingerprint and fingerprint in locked_to:
        return redirect(url_for("download_page", token=token) + "?approved=1")
    return render_template("request_device.html",
                           token=token, filename=entry["filename"],
                           fingerprint=fingerprint,
                           mobile=session.get(f"mob_{token}", ""),
                           already=True, contact_saved=contact_saved)

# ── APPROVAL STATUS POLL (called every 1s by client JS) ──────────────────────
@app.route("/download/<token>/status")
def download_status(token):
    """Returns JSON {approved: bool} — used by 1-second polling on pending page."""
    links       = load_json(LINKS_DB)
    entry       = links.get(token)
    if not entry:
        return jsonify({"approved": False, "error": "invalid"})
    fingerprint = request.args.get("fp", "")
    locked_to   = entry.get("locked_to", [])
    if isinstance(locked_to, str): locked_to = [locked_to]
    approved = bool(fingerprint and fingerprint in locked_to)
    return jsonify({"approved": approved})

# ── DOWNLOAD INFO (file size, expiry, download count) ────────────────────────
@app.route("/download/<token>/info")
def download_info(token):
    links   = load_json(LINKS_DB)
    entry   = links.get(token)
    if not entry:
        return jsonify({"error": "invalid"}), 404
    history = load_json(HISTORY_DB)
    dl_count = sum(1 for r in history.values() if r.get("token") == token)
    fp = Path(entry.get("file_path", ""))
    file_size = fp.stat().st_size if fp.is_file() else None
    return jsonify({
        "filename":           entry.get("filename", ""),
        "expires_at":         entry.get("expires_at", ""),
        "download_count":     dl_count,
        "file_size":          file_size,
        "mode":               entry.get("mode", "locked"),
        "password_protected": bool(entry.get("link_password_hash")),
    })

# ── SUBMIT CONTACT ────────────────────────────────────────────────────────────
@app.route("/download/<token>/contact", methods=["POST"])
def submit_contact(token):
    contact     = request.form.get("contact", "").strip()
    fingerprint = request.form.get("fingerprint", "") or session.get(f"fp_{token}", "")
    if contact and fingerprint:
        reqs = load_json(REQS_DB)
        matched = False
        for rid, r in reqs.items():
            if (r.get("token") == token and
                    r.get("fingerprint") == fingerprint and
                    r.get("status") == "pending"):
                if "@" in contact:
                    r["email"] = contact
                    r["name"]  = r.get("name") or contact
                else:
                    r["phone"] = contact   # always overwrite with latest
                    r["name"]  = r.get("name") or contact
                reqs[rid] = r
                matched = True
                break
        if not matched:
            # No existing pending req — create one so admin can see the mobile
            rid = uuid.uuid4().hex[:8].upper()
            reqs[rid] = {
                "name":        contact if "@" not in contact else "",
                "phone":       contact if "@" not in contact else "",
                "email":       contact if "@" in contact else "",
                "filename":    load_json(LINKS_DB).get(token, {}).get("filename", ""),
                "token":       token,
                "fingerprint": fingerprint,
                "status":      "pending",
                "created_at":  datetime.utcnow().isoformat(),
            }
        save_json(REQS_DB, reqs)
        # Persist in session so log_download finds it on auto-download
        session[f"mob_{token}"] = contact
    return redirect(url_for("download_pending", token=token, saved=1))

# ── CLIENT: manual request access — REMOVED ──────────────────────────────────
@app.route("/request-access")
def request_access():
    """Disabled — returns 404."""
    abort(404)

# ── RESET PENDING REQUESTS ────────────────────────────────────────────────────
@app.route("/admin/reset-pending", methods=["POST"])
def reset_pending():
    if not is_logged_in(): return redirect(url_for("login"))
    reqs = load_json(REQS_DB)
    cleared = 0
    for rid in list(reqs.keys()):
        if reqs[rid].get("status") == "pending":
            del reqs[rid]
            cleared += 1
    save_json(REQS_DB, reqs)
    flash(f"🗑 {cleared} pending request(s) cleared.", "info")
    return redirect(url_for("admin"))

# ── AJAX UPLOAD ENDPOINT ─────────────────────────────────────────────────────
@app.route("/admin/upload-ajax", methods=["POST"])
def upload_ajax():
    """Receive files via XHR/fetch, save to uploaded_files/, return token+link."""
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 403

    uploaded = request.files.getlist("upload_files")
    uploaded = [f for f in uploaded if f and f.filename]
    if not uploaded:
        return jsonify({"error": "No files received"}), 400

    days = int(request.form.get("days", 30))
    category = request.form.get("category", "").strip()
    link_password_raw = request.form.get("link_password", "").strip()
    link_password_hash = hash_pw(link_password_raw) if link_password_raw else None
    mode = request.form.get("mode", "locked").strip()
    if mode not in ("locked", "open"):
        mode = "locked"
    links = load_json(LINKS_DB)
    shorts = load_json(SHORTS_DB)
    created = []

    if len(uploaded) > 1:
        # Zip all into one archive
        zip_name = request.form.get("zip_name", "").strip() or "files"
        safe_zip = "".join(c for c in zip_name if c.isalnum() or c in "._- ").strip() or "files"
        file_uid = uuid.uuid4().hex[:8]
        dest_dir = UPLOAD_DIR / file_uid
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / f"{safe_zip}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in uploaded:
                rel = f.filename.replace("\\", "/")
                zf.writestr(rel, f.read())
        token      = uuid.uuid4().hex
        expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
        code       = make_short_code()
        shorts[code] = token
        links[token] = {
            "file_path":          str(zip_path),
            "filename":           zip_path.name,
            "expires_at":         expires_at,
            "locked_to":          [],
            "created_at":         datetime.utcnow().isoformat(),
            "short_code":         code,
            "file_count":         len(uploaded),
            "category":           category,
            "mode":               mode,
            "link_password_hash": link_password_hash,
            "link_password_plain": link_password_raw if link_password_raw else None,

        }
        base = get_base_url(request)
        created.append({
            "filename":           zip_path.name,
            "token":              token,
            "link":               base + "download/" + token,
            "short":              base + "s/" + code,
            "file_count":         len(uploaded),
            "mode":               mode,
            "password_protected": bool(link_password_hash),
        })
    else:
        for f in uploaded:
            safe_name = Path(f.filename).name
            file_uid  = uuid.uuid4().hex[:8]
            dest_dir  = UPLOAD_DIR / file_uid
            dest_dir.mkdir(parents=True, exist_ok=True)
            save_path = dest_dir / safe_name
            f.save(str(save_path))
            token      = uuid.uuid4().hex
            expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
            code       = make_short_code()
            shorts[code] = token
            links[token] = {
                "file_path":            str(save_path),
                "filename":             safe_name,
                "expires_at":           expires_at,
                "locked_to":            [],
                "created_at":           datetime.utcnow().isoformat(),
                "short_code":           code,
                "file_count":           1,
                "category":             category,
                "mode":                 mode,
                "link_password_hash":   link_password_hash,
                "link_password_plain":  link_password_raw if link_password_raw else None,
            }
            base = get_base_url(request)
            created.append({
                "filename":           safe_name,
                "token":              token,
                "link":               base + "download/" + token,
                "short":              base + "s/" + code,
                "file_count":         1,
                "password_protected": bool(link_password_hash),
            })

    save_json(LINKS_DB, links)
    save_json(SHORTS_DB, shorts)
    return jsonify({"created": created})

# ── CHUNKED UPLOAD — receive one chunk ───────────────────────────────────────
@app.route("/admin/upload-chunk", methods=["POST"])
def upload_chunk():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 403

    upload_id    = request.form.get("upload_id", "").strip()
    file_idx     = request.form.get("file_index", "0")
    chunk_idx    = int(request.form.get("chunk_index", 0))
    total_chunks = int(request.form.get("total_chunks", 1))
    filename     = request.form.get("filename", "file")
    chunk_blob   = request.files.get("chunk")

    if not upload_id or not chunk_blob:
        return jsonify({"error": "Missing data"}), 400

    chunk_dir = CHUNK_DIR / upload_id / str(file_idx)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Write metadata once per file-slot
    meta_path = CHUNK_DIR / upload_id / f"meta_{file_idx}.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "filename":     filename,
            "total_chunks": total_chunks,
        }))

    chunk_path = chunk_dir / f"{chunk_idx:05d}"
    chunk_blob.save(str(chunk_path))
    return jsonify({"ok": True, "chunk": chunk_idx, "file": file_idx})

# ── CHUNKED UPLOAD — resume: return already-uploaded chunks ──────────────────
@app.route("/admin/upload-resume/<upload_id>")
def upload_resume(upload_id):
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 403

    base = CHUNK_DIR / upload_id
    if not base.exists():
        return jsonify({"files": {}})

    result = {}
    for slot in base.iterdir():
        if slot.is_dir():
            done = sorted(
                int(p.name) for p in slot.iterdir()
                if p.is_file() and p.name.isdigit()
            )
            result[slot.name] = done
    return jsonify({"files": result})

# ── CHUNKED UPLOAD — finalize: assemble + create link ────────────────────────
@app.route("/admin/upload-finalize", methods=["POST"])
def upload_finalize():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 403

    data         = request.get_json()
    upload_id    = data.get("upload_id", "")
    files_meta   = data.get("files", [])   # [{name, rel, total_chunks}]
    days         = int(data.get("days", 30))
    category     = data.get("category", "").strip()
    mode         = data.get("mode", "locked").strip()
    zip_name     = data.get("zip_name", "").strip()
    label_raw    = data.get("label", "").strip()
    share_mode   = data.get("share_mode", "zip").strip()   # "zip" | "folder"
    link_password_raw  = data.get("link_password", "").strip()
    link_password_hash = hash_pw(link_password_raw) if link_password_raw else None
    if mode not in ("locked", "open"):
        mode = "locked"

    upload_base  = CHUNK_DIR / upload_id
    links_db     = load_json(LINKS_DB)
    shorts_db    = load_json(SHORTS_DB)
    created      = []

    def assemble(file_idx, total_chunks, dest_path):
        slot = upload_base / str(file_idx)
        with open(dest_path, "wb") as out:
            for i in range(total_chunks):
                cp = slot / f"{i:05d}"
                if cp.exists():
                    out.write(cp.read_bytes())

    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()

    if len(files_meta) == 1:
        fm        = files_meta[0]
        safe_name = Path(fm["name"]).name
        file_uid  = uuid.uuid4().hex[:8]
        dest_dir  = UPLOAD_DIR / file_uid
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_path = dest_dir / safe_name
        assemble(0, fm["total_chunks"], final_path)

        token = uuid.uuid4().hex
        code  = make_short_code()
        shorts_db[code] = token
        links_db[token] = {
            "file_path":           str(final_path),
            "filename":            safe_name,
            "label":               label_raw or safe_name,
            "expires_at":          expires_at,
            "locked_to":           [],
            "created_at":          datetime.utcnow().isoformat(),
            "short_code":          code,
            "file_count":          1,
            "category":            category,
            "mode":                mode,
            "link_password_hash":  link_password_hash,
            "link_password_plain": link_password_raw if link_password_raw else None,

        }
        base_url = get_base_url(request)
        created.append({
            "filename":           safe_name,
            "token":              token,
            "link":               base_url + "download/" + token,
            "short":              base_url + "s/" + code,
            "file_count":         1,
            "password_protected": bool(link_password_hash),
        })
    elif share_mode == "folder":
        # ── FOLDER SHARING: keep files unzipped so recipients browse online ──
        folder_label = zip_name or label_raw or "Shared Folder"
        safe_folder  = "".join(c for c in folder_label if c.isalnum() or c in "._- ").strip() or "Shared Folder"
        file_uid = uuid.uuid4().hex[:8]
        dest_dir = UPLOAD_DIR / file_uid
        dest_dir.mkdir(parents=True, exist_ok=True)
        rel_files = []
        for idx, fm in enumerate(files_meta):
            rel = (fm.get("rel") or fm["name"]).replace("\\", "/").lstrip("/")
            # Guard against path traversal in client-supplied relative paths
            safe_parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
            rel = "/".join(safe_parts) or fm["name"]
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            assemble(idx, fm["total_chunks"], target)
            rel_files.append(rel)

        token = uuid.uuid4().hex
        code  = make_short_code()
        shorts_db[code] = token
        links_db[token] = {
            "file_path":           str(dest_dir),
            "filename":            safe_folder,
            "label":               label_raw or safe_folder,
            "is_folder":           True,
            "folder_dir":          str(dest_dir),
            "files":               sorted(rel_files),
            "expires_at":          expires_at,
            "locked_to":           [],
            "created_at":          datetime.utcnow().isoformat(),
            "short_code":          code,
            "file_count":          len(rel_files),
            "category":            category,
            "mode":                mode,
            "link_password_hash":  link_password_hash,
            "link_password_plain": link_password_raw if link_password_raw else None,
        }
        base_url = get_base_url(request)
        created.append({
            "filename":           safe_folder,
            "token":              token,
            "link":               base_url + "download/" + token,
            "short":              base_url + "s/" + code,
            "file_count":         len(rel_files),
            "is_folder":          True,
            "password_protected": bool(link_password_hash),
        })
    else:
        safe_zip = "".join(c for c in zip_name if c.isalnum() or c in "._- ").strip() or "files"
        file_uid = uuid.uuid4().hex[:8]
        dest_dir = UPLOAD_DIR / file_uid
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / f"{safe_zip}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, fm in enumerate(files_meta):
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                assemble(idx, fm["total_chunks"], tmp_path)
                rel = fm.get("rel") or fm["name"]
                zf.write(str(tmp_path), rel)
                tmp_path.unlink(missing_ok=True)

        token = uuid.uuid4().hex
        code  = make_short_code()
        shorts_db[code] = token
        links_db[token] = {
            "file_path":           str(zip_path),
            "filename":            zip_path.name,
            "label":               label_raw or zip_path.name,
            "expires_at":          expires_at,
            "locked_to":           [],
            "created_at":          datetime.utcnow().isoformat(),
            "short_code":          code,
            "file_count":          len(files_meta),
            "category":            category,
            "mode":                mode,
            "link_password_hash":  link_password_hash,
            "link_password_plain": link_password_raw if link_password_raw else None,

        }
        base_url = get_base_url(request)
        created.append({
            "filename":           zip_path.name,
            "token":              token,
            "link":               base_url + "download/" + token,
            "short":              base_url + "s/" + code,
            "file_count":         len(files_meta),
            "password_protected": bool(link_password_hash),
        })

    save_json(LINKS_DB, links_db)
    save_json(SHORTS_DB, shorts_db)

    # Clean up chunk temp dir
    shutil.rmtree(str(upload_base), ignore_errors=True)

    return jsonify({"created": created})
@app.route("/admin/set-label/<token>", methods=["POST"])
def set_label(token):
    if not is_logged_in():
        return redirect(url_for("login"))
    links = load_json(LINKS_DB)
    if token in links:
        new_label = request.form.get("label", "").strip()
        links[token]["label"] = new_label or links[token].get("filename", "")
        save_json(LINKS_DB, links)
        flash("✅ Preview label updated.", "success")
    return redirect(url_for("admin"))

def delete_uploaded(token):
    """Internal helper — call only from within a logged-in route."""
    links  = load_json(LINKS_DB)
    shorts = load_json(SHORTS_DB)
    entry  = links.get(token)
    if entry:
        fp = Path(entry.get("file_path", ""))
        try:
            if fp.is_file():
                fp.unlink()
            if fp.parent.exists() and not any(fp.parent.iterdir()):
                fp.parent.rmdir()
        except Exception:
            pass
        code = entry.get("short_code")
        if code:
            shorts.pop(code, None)
        del links[token]
        save_json(LINKS_DB, links)
        save_json(SHORTS_DB, shorts)
        flash("🗑 File and link deleted.", "info")

@app.route("/admin/delete/<token>", methods=["POST"])
def admin_delete(token):
    """Route-registered wrapper so delete can be linked from templates."""
    if not is_logged_in():
        return redirect(url_for("login"))
    delete_uploaded(token)
    return redirect(url_for("admin"))

# ── 2FA SETUP ─────────────────────────────────────────────────────────────────
@app.route("/admin/2fa", methods=["GET", "POST"])
def setup_2fa():
    if not is_logged_in(): return redirect(url_for("login"))
    if not TOTP_AVAILABLE:
        flash("❌ pyotp / qrcode not installed. Run: pip install pyotp qrcode[pil]", "error")
        return redirect(url_for("admin"))

    error   = None
    qr_b64  = None
    secret  = None
    cfg     = get_config()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate":
            secret = pyotp.random_base32()
            session["pending_totp_secret"] = secret
            qr_b64 = generate_totp_qr(secret)
            return render_template("setup_2fa.html",
                                   qr_b64=qr_b64, secret=secret,
                                   enabled=is_2fa_enabled(), error=None)

        elif action == "verify":
            secret = session.get("pending_totp_secret")
            if not secret:
                error = "Session expired. Please generate a new QR code."
            else:
                code = request.form.get("totp_code", "").strip().replace(" ", "")
                tmp_totp = pyotp.TOTP(secret)
                if tmp_totp.verify(code, valid_window=1):
                    cfg["totp_secret"] = secret
                    save_config(cfg)
                    session.pop("pending_totp_secret", None)
                    flash("✅ Google Authenticator 2FA enabled successfully!", "success")
                    return redirect(url_for("admin"))
                error = "Code incorrect. Please try again with a fresh code."
                qr_b64 = generate_totp_qr(secret)
            return render_template("setup_2fa.html",
                                   qr_b64=qr_b64, secret=secret,
                                   enabled=is_2fa_enabled(), error=error)

        elif action == "disable":
            pw = request.form.get("password", "")
            if check_admin(pw):
                cfg.pop("totp_secret", None)
                save_config(cfg)
                flash("✅ 2FA disabled.", "info")
                return redirect(url_for("admin"))
            error = "Incorrect password. 2FA not disabled."

    return render_template("setup_2fa.html",
                           qr_b64=None, secret=None,
                           enabled=is_2fa_enabled(), error=error)

# ── LINK PASSWORD MANAGER ─────────────────────────────────────────────────────
@app.route("/admin/link-passwords")
def link_passwords():
    if not is_logged_in(): return redirect(url_for("login"))
    links   = load_json(LINKS_DB)
    shorts  = load_json(SHORTS_DB)
    now     = datetime.utcnow().isoformat()[:10]
    rows    = []
    for token, l in links.items():
        if not l.get("link_password_hash"):
            continue
        # Skip expired links — they'll be auto-deleted anyway
        if l.get("expires_at","")[:10] < now:
            continue
        code = l.get("short_code", "")
        rows.append({
            "token":      token,
            "filename":   l.get("label") or l.get("filename", ""),
            "password":   l.get("link_password_plain") or "••••••••",
            "short_code": code,
            "expires_at": l.get("expires_at", "")[:10],
            "category":   l.get("category", ""),
        })
    # Sort: category A→Z, then expiry newest first
    rows.sort(key=lambda r: (r["category"].lower(), r["expires_at"]), reverse=False)
    rows.sort(key=lambda r: r["expires_at"], reverse=True)
    rows.sort(key=lambda r: r["category"].lower())
    return render_template("link_passwords.html", rows=rows)

@app.route("/admin/categories/reorder", methods=["POST"])
def reorder_categories():
    """Accept a JSON list of category names in the new order and persist it."""
    if not is_logged_in():
        return jsonify({"error": "not_logged_in"}), 403
    data = request.get_json(silent=True) or {}
    order = data.get("order", [])
    if not isinstance(order, list):
        return jsonify({"error": "invalid"}), 400
    existing = get_categories()
    # Keep only names that exist; append any missing ones at the end
    seen   = set()
    merged = []
    for name in order:
        if name in existing and name not in seen:
            merged.append(name)
            seen.add(name)
    for name in existing:
        if name not in seen:
            merged.append(name)
    save_categories(merged)
    return jsonify({"ok": True, "order": merged})

@app.route("/admin/categories", methods=["GET", "POST"])
def manage_categories():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        name   = request.form.get("name", "").strip()
        old    = request.form.get("old_name", "").strip()
        cats   = get_categories()

        if action == "add":
            if name and name not in cats:
                cats.append(name)
                save_categories(cats)
                flash(f"✅ Category '{name}' added.", "success")
            elif name in cats:
                flash(f"⚠ Category '{name}' already exists.", "error")

        elif action == "edit":
            if old in cats and name and name != old:
                idx = cats.index(old)
                cats[idx] = name
                save_categories(cats)
                # rename on existing links
                links = load_json(LINKS_DB)
                for l in links.values():
                    if l.get("category") == old:
                        l["category"] = name
                save_json(LINKS_DB, links)
                flash(f"✅ Category renamed to '{name}'.", "success")

        elif action == "delete":
            if name in cats:
                cats.remove(name)
                save_categories(cats)
                flash(f"🗑 Category '{name}' deleted.", "info")

        return redirect(url_for("manage_categories"))

    # GET — build link counts per category, sorted alphabetically
    cats  = sorted(get_categories(), key=lambda c: c.lower())
    links = load_json(LINKS_DB)
    cat_link_counts = {}
    for l in links.values():
        c = l.get("category", "")
        if c:
            cat_link_counts[c] = cat_link_counts.get(c, 0) + 1

    return render_template("categories.html",
                           categories=cats,
                           cat_link_counts=cat_link_counts)

# ── OG THUMBNAIL (1200x630 PNG, no Pillow needed) ────────────────────────────
import struct, zlib as _zlib

def _make_solid_png(width, height, rgb):
    """Build a minimal valid PNG with a solid colour."""
    r, g, b = rgb
    def _chunk(tag, data):
        crc = struct.pack('>I', _zlib.crc32(tag + data) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + tag + data + crc
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    row  = b'\x00' + bytes([r, g, b] * width)
    idat = _zlib.compress(row * height, 1)
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', idat)
            + _chunk(b'IEND', b''))

# Pre-build a 1200×630 dark-navy PNG (matches app brand colour #080a0f ≈ 8,10,15)
_OG_PNG_BYTES = _make_solid_png(1200, 630, (8, 10, 15))

@app.route("/og-thumb/<token>.png")
def og_thumb(token):
    links = load_json(LINKS_DB)
    if token not in links:
        abort(404)
    from flask import Response
    return Response(_OG_PNG_BYTES,
                    mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


# ── UNIFIED SETTINGS PAGE ────────────────────────────────────────────────────
@app.route("/admin/settings", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def admin_settings():
    if not is_logged_in(): return redirect(url_for("login"))

    cfg     = get_config()
    error   = {}
    success = {}
    tab     = request.args.get("tab", "profile")

    if request.method == "POST":
        action = request.form.get("action")
        tab    = request.form.get("tab", "profile")

        if action == "save_profile":
            name = request.form.get("display_name", "").strip()
            cfg["display_name"] = name or "Admin"
            save_config(cfg)
            flash("✅ Profile updated.", "success")
            return redirect(url_for("admin_settings", tab="profile"))

        elif action == "change_password":
            old = request.form.get("old_password", "")
            pw  = request.form.get("password", "")
            pw2 = request.form.get("confirm", "")
            if not check_admin(old):
                error["password"] = "Current password is incorrect."
            elif len(pw) < 6:
                error["password"] = "New password must be at least 6 characters."
            elif pw != pw2:
                error["password"] = "Passwords do not match."
            else:
                cfg["password_hash"] = hash_pw(pw)
                save_config(cfg)
                flash("✅ Password changed.", "success")
                return redirect(url_for("admin_settings", tab="password"))

        elif action == "save_smtp":
            smtp = {
                "host":      request.form.get("host", "").strip(),
                "port":      int(request.form.get("port", 587) or 587),
                "user":      request.form.get("user", "").strip(),
                "password":  request.form.get("smtp_password", "").strip(),
                "from_addr": request.form.get("from_addr", "").strip(),
                "use_ssl":   request.form.get("use_ssl") == "1",
            }
            cfg["smtp"]           = smtp
            cfg["recovery_email"] = request.form.get("recovery_email", "").strip().lower()
            save_config(cfg)
            flash("✅ SMTP settings saved.", "success")
            return redirect(url_for("admin_settings", tab="smtp"))

        elif action == "test_smtp":
            to = cfg.get("recovery_email", cfg.get("smtp", {}).get("user", ""))
            if to and send_otp_email(to, "123456"):
                flash(f"✅ Test email sent to {to}.", "success")
            else:
                flash("❌ Test failed. Check SMTP settings.", "error")
            return redirect(url_for("admin_settings", tab="smtp"))

        elif action == "2fa_generate":
            if TOTP_AVAILABLE:
                secret = pyotp.random_base32()
                session["pending_totp_secret"] = secret
                qr_b64 = generate_totp_qr(secret)
                return render_template("settings.html",
                    tab="2fa", cfg=cfg, smtp=cfg.get("smtp", {}),
                    recovery_email=cfg.get("recovery_email", ""),
                    two_fa_enabled=is_2fa_enabled(),
                    qr_b64=qr_b64, totp_secret=secret,
                    error=error, success=success)
            flash("❌ pyotp not installed.", "error")
            return redirect(url_for("admin_settings", tab="2fa"))

        elif action == "2fa_verify":
            secret = session.get("pending_totp_secret")
            code   = request.form.get("totp_code", "").strip().replace(" ", "")
            if not secret:
                flash("Session expired. Generate QR again.", "error")
                return redirect(url_for("admin_settings", tab="2fa"))
            tmp = pyotp.TOTP(secret)
            if tmp.verify(code, valid_window=1):
                cfg["totp_secret"] = secret
                save_config(cfg)
                session.pop("pending_totp_secret", None)
                flash("✅ 2FA enabled.", "success")
                return redirect(url_for("admin_settings", tab="2fa"))
            else:
                qr_b64 = generate_totp_qr(secret)
                return render_template("settings.html",
                    tab="2fa", cfg=cfg, smtp=cfg.get("smtp", {}),
                    recovery_email=cfg.get("recovery_email", ""),
                    two_fa_enabled=is_2fa_enabled(),
                    qr_b64=qr_b64, totp_secret=secret,
                    error={"2fa": "Incorrect code. Try again."}, success=success)

        elif action == "2fa_disable":
            pw = request.form.get("disable_pw", "")
            if check_admin(pw):
                cfg.pop("totp_secret", None)
                save_config(cfg)
                flash("✅ 2FA disabled.", "info")
            else:
                flash("Incorrect password.", "error")
            return redirect(url_for("admin_settings", tab="2fa"))

        elif action == "save_site":
            cfg["site_name"]        = request.form.get("site_name", "FileShare").strip() or "FileShare"
            cfg["max_upload_mb"]    = max(1, int(request.form.get("max_upload_mb", 500) or 500))
            cfg["default_expiry"]   = max(1, int(request.form.get("default_expiry", 30) or 30))
            cfg["max_downloads"]    = max(0, int(request.form.get("max_downloads", 0) or 0))
            cfg["session_timeout"]  = max(5, int(request.form.get("session_timeout", 60) or 60))
            cfg["notify_email"]     = request.form.get("notify_email", "").strip().lower()
            cfg["notify_on_request"]= request.form.get("notify_on_request") == "1"
            cfg["notify_on_download"]= request.form.get("notify_on_download") == "1"
            save_config(cfg)
            # Apply session timeout
            app.permanent_session_lifetime = timedelta(minutes=cfg["session_timeout"])
            flash("✅ Site settings saved.", "success")
            return redirect(url_for("admin_settings", tab="site"))

        elif action == "save_branding":
            cfg["brand_logo_url"]   = request.form.get("brand_logo_url", "").strip()
            cfg["brand_tagline"]    = request.form.get("brand_tagline", "").strip()
            cfg["brand_footer"]     = request.form.get("brand_footer", "").strip()
            cfg["brand_accent"]     = request.form.get("brand_accent", "#00d4ff").strip()
            save_config(cfg)
            flash("✅ Branding saved.", "success")
            return redirect(url_for("admin_settings", tab="branding"))

        elif action == "toggle_maintenance":
            cfg["maintenance_mode"]    = request.form.get("maintenance_mode") == "1"
            cfg["maintenance_message"] = request.form.get("maintenance_message", "").strip() or "Site is under maintenance. Please check back soon."
            save_config(cfg)
            state = "enabled" if cfg["maintenance_mode"] else "disabled"
            flash(f"✅ Maintenance mode {state}.", "success")
            return redirect(url_for("admin_settings", tab="site"))

        return redirect(url_for("admin_settings", tab=tab))

    return render_template("settings.html",
        tab=tab,
        cfg=cfg,
        smtp=cfg.get("smtp", {}),
        recovery_email=cfg.get("recovery_email", ""),
        two_fa_enabled=is_2fa_enabled(),
        totp_available=TOTP_AVAILABLE,
        qr_b64=None, totp_secret=None,
        error=error, success=success)

@app.before_request
def check_maintenance():
    cfg = load_json(Path("config.json"))
    if not cfg.get("maintenance_mode"):
        return
    allowed = ["/admin", "/login", "/logout", "/setup", "/forgot", "/static", "/og-thumb"]
    if any(request.path.startswith(p) for p in allowed):
        return
    if session.get("admin_logged_in"):
        return
    msg = cfg.get("maintenance_message", "Site is under maintenance. Please check back soon.")
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Maintenance</title>
<style>body{{margin:0;background:#080a0f;color:#e8eaf2;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;text-align:center}}
.box{{max-width:480px;padding:40px}}.icon{{font-size:56px;margin-bottom:16px}}
h1{{font-size:1.8rem;margin:0 0 12px;color:#00d4ff}}p{{color:#6b7494;font-size:15px;line-height:1.6}}
</style></head><body><div class="box"><div class="icon">🔧</div>
<h1>Under Maintenance</h1><p>{msg}</p></div></body></html>""", 503

# ── LIVE STATS API (for Refresh button — no restart needed) ──────────────────
@app.route("/admin/stats")
def admin_stats():
    if not is_logged_in():
        return jsonify({"error": "not_logged_in"}), 403

    # Auto-delete expired links on every refresh (same as page load)
    cfg_now      = get_config()
    grace        = int(cfg_now.get("expiry_grace_days", -1))
    auto_deleted = auto_delete_expired_links(grace)

    links   = load_json(LINKS_DB)
    reqs    = load_json(REQS_DB)
    history = load_json(HISTORY_DB)
    now     = datetime.utcnow().isoformat()[:10]
    pending = {k: v for k, v in reqs.items() if v.get("status") == "pending"}
    active  = sum(1 for l in links.values() if l.get("expires_at","")[:10] >= now)
    expired = sum(1 for l in links.values() if l.get("expires_at","")[:10] < now)
    shorts  = load_json(SHORTS_DB)
    base    = get_base_url(request)
    links_list = []
    for tok, l in links.items():
        code = l.get("short_code","")
        links_list.append({
            "token":      tok,
            "filename":   l.get("label") or l.get("filename",""),
            "expires_at": l.get("expires_at","")[:10],
            "days_left":  days_left(l.get("expires_at","")),
            "short_url":  (base + "s/" + code) if code else "",
            "full_url":   base + "download/" + tok,
            "category":   l.get("category",""),
            "mode":       l.get("mode","locked"),
            "pw":         bool(l.get("link_password_hash")),
            "file_count": l.get("file_count",1),
        })
    links_list.sort(key=lambda x: x["expires_at"], reverse=True)
    return jsonify({
        "download_count": len(history),
        "active_links":   active,
        "total_links":    len(links),
        "pending_count":  len(pending),
        "expired_count":  expired,
        "links":          links_list,
        "categories":     get_categories(),
        "auto_deleted":   auto_deleted,
    })


import re as _re
from flask import Response

# ════════════════════════════════════════════════════════════════════════════
#  FEATURE EXTENSIONS
#  1. Per-link analytics (views / downloads / unique visitors / geo / UA)
#  2. QR codes for share links
#  5. Folder sharing (browse online)            6-9. Inline viewers
#  10. Link branding (custom slugs)
# ════════════════════════════════════════════════════════════════════════════
ANALYTICS_DB = Path("analytics.json")
SLUGS_DB     = Path("slugs.json")

# Single-segment paths that must never be claimed as a custom slug.
RESERVED_SLUGS = {
    "", "s", "l", "qr", "download", "admin", "login", "logout", "setup",
    "forgot", "change-password", "request-access", "static", "og-thumb",
    "api", "favicon.ico", "robots.txt",
}
SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")

# ── File-type classification (for viewers) ───────────────────────────────────
IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "avif", "ico"}
VIDEO_EXTS = {"mp4", "webm", "ogv", "mov", "m4v", "mkv"}
AUDIO_EXTS = {"mp3", "wav", "aac", "m4a", "oga", "ogg", "flac", "opus"}
PDF_EXTS   = {"pdf"}
TEXT_EXTS  = {"txt", "md", "csv", "log", "json", "xml", "yml", "yaml"}

def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""

def file_kind(name: str) -> str:
    e = _ext(name)
    if e in IMAGE_EXTS: return "image"
    if e in VIDEO_EXTS: return "video"
    if e in AUDIO_EXTS: return "audio"
    if e in PDF_EXTS:   return "pdf"
    if e in TEXT_EXTS:  return "text"
    return "other"

def viewer_kind(entry: dict) -> str:
    """What inline viewer (if any) a link supports — drives the Preview button."""
    if entry.get("is_folder"):
        return "folder"
    return file_kind(entry.get("filename", ""))

# ── User-Agent parsing (dependency-free) ─────────────────────────────────────
def parse_ua(ua: str):
    u = (ua or "").lower()
    if   "windows"   in u: os_name = "Windows"
    elif "android"   in u: os_name = "Android"
    elif "iphone" in u or "ipad" in u or "ipod" in u: os_name = "iOS"
    elif "mac os" in u or "macintosh" in u: os_name = "macOS"
    elif "cros"      in u: os_name = "ChromeOS"
    elif "linux"     in u: os_name = "Linux"
    else: os_name = "Unknown"

    if   "edg"            in u: browser = "Edge"
    elif "opr" in u or "opera" in u: browser = "Opera"
    elif "samsungbrowser" in u: browser = "Samsung Internet"
    elif "fxios" in u or "firefox" in u: browser = "Firefox"
    elif "chrome" in u and "chromium" not in u: browser = "Chrome"
    elif "chromium"       in u: browser = "Chromium"
    elif "safari"         in u: browser = "Safari"
    elif any(b in u for b in ("bot", "crawler", "spider")): browser = "Bot"
    else: browser = "Unknown"

    if "ipad" in u or "tablet" in u or ("android" in u and "mobile" not in u):
        device = "Tablet"
    elif "mobi" in u or "iphone" in u or "android" in u:
        device = "Mobile"
    else:
        device = "Desktop"
    return browser, os_name, device

_COUNTRY_NAMES = {
    "US": "United States", "IN": "India", "GB": "United Kingdom", "CA": "Canada",
    "AU": "Australia", "DE": "Germany", "FR": "France", "NL": "Netherlands",
    "SG": "Singapore", "AE": "UAE", "SA": "Saudi Arabia", "JP": "Japan",
    "CN": "China", "BR": "Brazil", "ZA": "South Africa", "NG": "Nigeria",
    "PK": "Pakistan", "BD": "Bangladesh", "ID": "Indonesia", "RU": "Russia",
    "IT": "Italy", "ES": "Spain", "MX": "Mexico", "KR": "South Korea",
}

def geo_from_request(req) -> str:
    # Cloudflare tunnel adds CF-IPCountry; honour it when present.
    code = (req.headers.get("CF-IPCountry") or "").upper().strip()
    if code and code not in ("XX", "T1"):
        return _COUNTRY_NAMES.get(code, code)
    return "Unknown"

def _client_ip(req) -> str:
    xff = req.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.headers.get("CF-Connecting-IP") or req.remote_addr or ""

def visitor_id(req, fp: str = "") -> str:
    if fp:
        return "fp:" + hashlib.sha256(fp.encode()).hexdigest()[:16]
    raw = _client_ip(req) + "|" + req.headers.get("User-Agent", "")
    return "ip:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

def record_event(token: str, kind: str, req, fp: str = ""):
    """Append a view/download analytics event for a link."""
    if _is_crawler(req.headers.get("User-Agent", "")):
        return
    browser, os_name, device = parse_ua(req.headers.get("User-Agent", ""))
    data  = load_json(ANALYTICS_DB)
    entry = data.get(token) or {"events": []}
    entry["events"].append({
        "kind":    kind,
        "ts":      datetime.utcnow().isoformat(),
        "visitor": visitor_id(req, fp),
        "country": geo_from_request(req),
        "browser": browser,
        "os":      os_name,
        "device":  device,
    })
    if len(entry["events"]) > 5000:
        entry["events"] = entry["events"][-5000:]
    data[token] = entry
    save_json(ANALYTICS_DB, data)

def compute_analytics(token: str) -> dict:
    events    = (load_json(ANALYTICS_DB).get(token) or {}).get("events", [])
    views     = [e for e in events if e.get("kind") == "view"]
    downloads = [e for e in events if e.get("kind") == "download"]
    uniq      = {e.get("visitor") for e in events if e.get("visitor")}
    uniq_dl   = {e.get("visitor") for e in downloads if e.get("visitor")}

    def breakdown(field):
        out = {}
        for e in events:
            key = e.get(field) or "Unknown"
            out[key] = out.get(key, 0) + 1
        total = sum(out.values()) or 1
        rows = sorted(out.items(), key=lambda x: -x[1])
        return [{"name": k, "count": v, "pct": round(v / total * 100)} for k, v in rows]

    tv = len(views)
    td = len(downloads)
    return {
        "total_views":     tv,
        "total_downloads": td,
        "unique_visitors": len(uniq),
        "unique_downloaders": len(uniq_dl),
        "conversion":      round(td / tv * 100) if tv else 0,
        "by_country":      breakdown("country"),
        "by_browser":      breakdown("browser"),
        "by_device":       breakdown("device"),
        "by_os":           breakdown("os"),
        "recent":          list(reversed(events[-40:])),
    }

# ── Custom-slug (link branding) helpers ──────────────────────────────────────
def get_slug_for(token: str):
    for slug, tok in load_json(SLUGS_DB).items():
        if tok == token:
            return slug
    return None

def share_url_for(token: str, req) -> str:
    base = get_base_url(req)
    slug = get_slug_for(token)
    if slug:
        return base + slug
    code = (load_json(LINKS_DB).get(token) or {}).get("short_code")
    if code:
        return base + "s/" + code
    return base + "download/" + token

# ── QR code generation ───────────────────────────────────────────────────────
def make_qr_png(data: str):
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@app.route("/qr/<token>.png")
def qr_png(token):
    links = load_json(LINKS_DB)
    if token not in links:
        abort(404)
    png = make_qr_png(share_url_for(token, request))
    if png is None:
        abort(404)
    headers = {"Cache-Control": "public, max-age=600"}
    if request.args.get("dl"):
        headers["Content-Disposition"] = f'attachment; filename="qr-{token[:8]}.png"'
    return Response(png, mimetype="image/png", headers=headers)

# ── Per-link analytics dashboard ─────────────────────────────────────────────
@app.route("/admin/analytics/<token>")
def link_analytics(token):
    if not is_logged_in():
        return redirect(url_for("login"))
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        flash("Link not found.", "error")
        return redirect(url_for("admin"))
    return render_template(
        "analytics.html",
        token=token,
        entry=entry,
        label=entry.get("label") or entry.get("filename", ""),
        share_url=share_url_for(token, request),
        slug=get_slug_for(token),
        stats=compute_analytics(token),
    )

# ── Set / clear a custom slug for a link ─────────────────────────────────────
@app.route("/admin/set-slug/<token>", methods=["POST"])
def set_slug(token):
    if not is_logged_in():
        return redirect(url_for("login"))
    links = load_json(LINKS_DB)
    if token not in links:
        flash("Link not found.", "error")
        return redirect(url_for("admin"))
    raw   = request.form.get("slug", "").strip().lower().lstrip("/")
    slugs = load_json(SLUGS_DB)
    # Drop any existing slug pointing at this token
    for s in list(slugs.keys()):
        if slugs[s] == token:
            del slugs[s]
    if not raw:
        save_json(SLUGS_DB, slugs)
        flash("✅ Custom link cleared.", "info")
        return redirect(url_for("admin"))
    if raw in RESERVED_SLUGS or not SLUG_RE.match(raw):
        flash("❌ Invalid custom link. Use 3–50 letters, numbers or hyphens.", "error")
        return redirect(url_for("admin"))
    if raw in slugs and slugs[raw] != token:
        flash(f"❌ '/{raw}' is already taken by another link.", "error")
        return redirect(url_for("admin"))
    slugs[raw] = token
    save_json(SLUGS_DB, slugs)
    flash(f"✅ Custom link set: /{raw}", "success")
    return redirect(url_for("admin"))

# ── Inline viewer authorization ──────────────────────────────────────────────
def _viewer_authorized(token: str, entry: dict, req) -> bool:
    if session.get(f"dl_ok_{token}"):
        return True
    # Frictionless preview for fully-open links (no password, no device lock)
    if entry.get("mode", "locked") == "open" and not entry.get("link_password_hash"):
        session[f"dl_ok_{token}"] = "open"
        return True
    return False

# ── Inline viewer page (image gallery / pdf / video / audio / folder) ────────
@app.route("/download/<token>/view")
def view_file(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return render_template("expired.html", reason="Invalid or revoked link."), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return render_template("expired.html", reason="This link has expired."), 410
    is_folder = bool(entry.get("is_folder"))
    files = []
    if is_folder:
        for rel in entry.get("files", []):
            files.append({"path": rel, "name": rel.split("/")[-1], "kind": file_kind(rel)})
    return render_template(
        "viewer.html",
        token=token,
        filename=entry["filename"],
        label=entry.get("label") or entry["filename"],
        kind="folder" if is_folder else file_kind(entry["filename"]),
        is_folder=is_folder,
        files=files,
        password_protected=bool(entry.get("link_password_hash")),
        mode=entry.get("mode", "locked"),
        share_url=share_url_for(token, request),
    )

# ── Inline file stream (Range-aware, served inline not as attachment) ────────
@app.route("/download/<token>/raw")
def raw_file(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        return jsonify({"error": "invalid"}), 404
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return jsonify({"error": "expired"}), 410
    if not _viewer_authorized(token, entry, request):
        return jsonify({"error": "not_verified"}), 403
    fp = Path(entry.get("file_path", ""))
    if entry.get("is_folder") or not fp.is_file():
        return jsonify({"error": "file_missing"}), 404
    return send_file(str(fp), as_attachment=False,
                     download_name=entry["filename"], conditional=True)

# ── Serve one file from inside a shared folder ───────────────────────────────
@app.route("/download/<token>/file")
def folder_file(token):
    links = load_json(LINKS_DB)
    entry = links.get(token)
    if not entry:
        abort(404)
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        abort(410)
    if not _viewer_authorized(token, entry, request):
        abort(403)
    rel = request.args.get("p", "")
    if rel not in entry.get("files", []):
        abort(404)
    folder_dir = Path(entry.get("folder_dir") or entry.get("file_path", "")).resolve()
    target     = (folder_dir / rel).resolve()
    if not str(target).startswith(str(folder_dir)) or not target.is_file():
        abort(404)
    as_dl = bool(request.args.get("dl"))
    record_event(token, "download" if as_dl else "view", request)
    return send_file(str(target), as_attachment=as_dl,
                     download_name=target.name, conditional=True)

# ── Branded short URL — must be registered LAST (catch-all single segment) ───
@app.route("/<slug>")
def branded(slug):
    token = load_json(SLUGS_DB).get(slug.lower())
    if not token:
        abort(404)
    return redirect(url_for("download_page", token=token))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
