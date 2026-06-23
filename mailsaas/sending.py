"""
Real email sending + open/click tracking.

Pure helpers used by the campaign-send pipeline:

  * ``make_token``    — unique per-message id used in tracking URLs
  * ``render_html``   — resolve merge tags, wrap links for click tracking, and
                        append the invisible open-tracking pixel
  * ``smtp_send``     — actually deliver one message over SMTP

Delivery is real when a transport is configured (per-server credentials or the
global ``MAILSAAS_SMTP_*`` relay). With no transport it runs in "dry-run" mode
so the pipeline, counters and tracking still work for local testing.
"""
import os
import re
import ssl
import smtplib
import secrets
from email.message import EmailMessage
from urllib.parse import quote


def make_token():
    return secrets.token_urlsafe(16)


_HREF_RE = re.compile(r'href="(https?://[^"]+)"', re.IGNORECASE)


def wrap_links(html, base_url, token):
    """Rewrite every http(s) link to pass through the click-tracking redirect."""
    def repl(m):
        url = m.group(1)
        return 'href="%s/t/c/%s?u=%s"' % (base_url, token, quote(url, safe=""))
    return _HREF_RE.sub(repl, html)


def render_html(body, contact, base_url, token):
    """Resolve merge tags, wrap links, and append the open-tracking pixel."""
    name = (contact.get("name") or contact["email"].split("@")[0]).strip()
    html = (body or "").replace("{{name}}", name).replace("{{email}}", contact["email"])
    # Treat plain-text bodies as text → wrap into simple HTML.
    if "<" not in html:
        html = "<p>" + html.replace("\n", "<br>") + "</p>"
    html = wrap_links(html, base_url, token)
    pixel = ('<img src="%s/t/o/%s.gif" width="1" height="1" alt="" '
             'style="display:none">' % (base_url, token))
    return html + pixel


def env_transport():
    """Global SMTP relay from the environment, or None if unset."""
    host = os.environ.get("MAILSAAS_SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("MAILSAAS_SMTP_PORT", "587")),
        "username": os.environ.get("MAILSAAS_SMTP_USER"),
        "password": os.environ.get("MAILSAAS_SMTP_PASS"),
        "from": os.environ.get("MAILSAAS_SMTP_FROM", "no-reply@mailsaas.io"),
        "tls": True,
    }


def server_transport(row):
    """Per-relay transport if the SMTP server row carries credentials."""
    pw = row["password"] if "password" in row.keys() else None
    if not (row["host"] and row["username"] and pw):
        return None
    return {
        "host": row["host"], "port": row["port"],
        "username": row["username"], "password": pw,
        "from": row["username"] if "@" in (row["username"] or "")
        else "no-reply@mailsaas.io",
        "tls": bool(row["use_tls"]) if "use_tls" in row.keys() else True,
    }


def smtp_send(cfg, to_addr, subject, html, from_addr=None):
    """Deliver one HTML email. Returns (ok, info)."""
    msg = EmailMessage()
    msg["From"] = from_addr or cfg.get("from") or "no-reply@mailsaas.io"
    msg["To"] = to_addr
    msg["Subject"] = subject or "(no subject)"
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
            s.ehlo()
            if cfg.get("tls", True):
                try:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                except smtplib.SMTPException:
                    pass  # server may not support STARTTLS
            if cfg.get("username") and cfg.get("password"):
                s.login(cfg["username"], cfg["password"])
            s.send_message(msg)
        return True, "delivered"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# A 1x1 transparent GIF returned by the open-tracking pixel.
PIXEL_GIF = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
    0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x21, 0xF9, 0x04, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3B,
])
