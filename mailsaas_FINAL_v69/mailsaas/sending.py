"""
Real email sending + open/click tracking — HARDENED.

Drop-in replacement for the previous sending.py. Every public name and call
signature is unchanged (`make_token`, `wrap_links`, `render_html`,
`env_transport`, `server_transport`, `smtp_send`, `PIXEL_GIF`) so the existing
campaign pipeline keeps working. New behaviour is added, not swapped:

  * Real text/plain alternative auto-generated from the HTML (was a dummy line)
  * DKIM signing when a key is configured (the #1 inbox-vs-spam lever)
  * Correct headers: Message-ID, Date, Reply-To, and the List-Unsubscribe +
    List-Unsubscribe-Post one-click pair (RFC 8058) that Gmail/Yahoo now
    require for bulk senders — auto-derived from the unsubscribe link already
    in the body, so no caller changes are needed
  * Connection reuse: pass conn= to send many messages over one SMTP session
  * classify_failure(): turn an SMTP error into hard/soft + suppress decision

DKIM config (per-relay cfg keys OR environment):
    cfg['dkim_domain'] / MAILSAAS_DKIM_DOMAIN
    cfg['dkim_selector'] / MAILSAAS_DKIM_SELECTOR   (default "mail")
    cfg['dkim_key'] (PEM string) or cfg['dkim_key_path'] /
        MAILSAAS_DKIM_KEY / MAILSAAS_DKIM_KEY_PATH
"""
import os
import re
import ssl
import html as _html
import smtplib
import secrets
from datetime import datetime, timezone
from email.utils import make_msgid, formatdate
from email.message import EmailMessage
from urllib.parse import quote


def make_token():
    return secrets.token_urlsafe(16)


_HREF_RE = re.compile(r'href="(https?://[^"]+)"', re.IGNORECASE)


def wrap_links(html, base_url, token):
    """Rewrite every http(s) link to pass through the click-tracking redirect."""
    def repl(m):
        url = m.group(1)
        # Don't double-wrap our own tracking/unsubscribe/view links.
        if "/t/c/" in url or "/t/u/" in url or "/v/" in url:
            return m.group(0)
        return 'href="%s/t/c/%s?u=%s"' % (base_url, token, quote(url, safe=""))
    return _HREF_RE.sub(repl, html)


def render_html(body, contact, base_url, token):
    """Resolve merge tags, wrap links, and append the open-tracking pixel."""
    name = (contact.get("name") or contact["email"].split("@")[0]).strip()
    unsub_url = "%s/t/u/%s" % (base_url, token)
    view_url = "%s/v/%s" % (base_url, token)
    values = {
        "name": name,
        "email": contact.get("email") or "",
        "company": (contact.get("company") or "").strip(),
        "mobile": (contact.get("mobile") or "").strip(),
        "city": (contact.get("city") or "").strip(),
        "state": (contact.get("state") or "").strip(),
        "country": (contact.get("country") or "").strip(),
        "balance": (contact.get("balance") or "").strip(),
        "last_purchase": (contact.get("last_purchase") or "").strip(),
    }

    def _sub(m):
        key = m.group(1).strip().lower()
        fallback = (m.group(2) or "").strip()
        if key in ("unsubscribe_url", "view_in_browser_url"):
            return m.group(0)
        return values.get(key) or fallback

    html = re.sub(r"\{\{\s*(\w+)\s*(?:\|\s*([^}]*))?\}\}", _sub, body or "")
    html = (html.replace("{{unsubscribe_url}}", unsub_url)
                .replace("{{view_in_browser_url}}", view_url))
    if "<" not in html:
        html = "<p>" + html.replace("\n", "<br>") + "</p>"
    html = wrap_links(html, base_url, token)
    pixel = ('<img src="%s/t/o/%s.gif" width="1" height="1" alt="" '
             'style="display:none">' % (base_url, token))
    if "/t/u/" in html or "unsubscribe" in html.lower():
        footer = ""
    else:
        footer = ('<hr><p style="font-size:11px;color:#888;text-align:center">'
                  'You received this because you subscribed. '
                  '<a href="%s">View in browser</a> &middot; '
                  '<a href="%s">Unsubscribe</a></p>' % (view_url, unsub_url))
    return html + footer + pixel


def render_subject(subject, contact):
    """Resolve merge tags in a subject line — variables ONLY, no link-wrapping,
    no tracking pixel, no footer. Supports the same {{field}} and
    {{field|fallback}} syntax as the body, for the fields available on a
    contact. The URL tokens ({{unsubscribe_url}}/{{view_in_browser_url}}) are
    meaningless in a subject, so they resolve to empty rather than a raw URL."""
    name = (contact.get("name") or (contact.get("email") or "").split("@")[0]).strip()
    values = {
        "name": name,
        "email": contact.get("email") or "",
        "company": (contact.get("company") or "").strip(),
        "mobile": (contact.get("mobile") or "").strip(),
        "city": (contact.get("city") or "").strip(),
        "state": (contact.get("state") or "").strip(),
        "country": (contact.get("country") or "").strip(),
        "balance": (contact.get("balance") or "").strip(),
        "last_purchase": (contact.get("last_purchase") or "").strip(),
    }

    def _sub(m):
        key = m.group(1).strip().lower()
        fallback = (m.group(2) or "").strip()
        if key in ("unsubscribe_url", "view_in_browser_url"):
            return ""
        return values.get(key) or fallback

    return re.sub(r"\{\{\s*(\w+)\s*(?:\|\s*([^}]*))?\}\}", _sub, subject or "")


# --------------------------------------------------------------------------- #
#  Plain-text generation (real, dependency-free)
# --------------------------------------------------------------------------- #
def html_to_text(html):
    """Produce a readable text/plain version of an HTML email.
    Not a full browser — just enough that text-only clients and spam filters
    see real words instead of a 'use an HTML client' stub."""
    if not html:
        return ""
    t = html
    # Drop invisible / non-content elements.
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r'(?i)<img[^>]*>', "", t)
    # Turn anchors into "text (url)".
    def _a(m):
        href = m.group(1)
        text = re.sub(r"(?s)<[^>]+>", "", m.group(2)).strip()
        if not href or href.startswith("#") or "/t/o/" in href:
            return text
        return "%s (%s)" % (text, href) if text else href
    t = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', _a, t)
    # Block-level breaks.
    t = re.sub(r"(?i)<(br|/p|/div|/h[1-6]|/tr)\s*/?>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "\n  - ", t)
    t = re.sub(r"(?i)<(p|div|h[1-6]|table|tr)[^>]*>", "\n", t)
    # Strip the rest of the tags, unescape entities.
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = _html.unescape(t)
    # Collapse whitespace.
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# --------------------------------------------------------------------------- #
#  Transports
# --------------------------------------------------------------------------- #
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
        "reply_to": os.environ.get("MAILSAAS_SMTP_REPLYTO"),
        "tls": True,
        "dkim_domain": os.environ.get("MAILSAAS_DKIM_DOMAIN"),
        "dkim_selector": os.environ.get("MAILSAAS_DKIM_SELECTOR", "mail"),
        "dkim_key": os.environ.get("MAILSAAS_DKIM_KEY"),
        "dkim_key_path": os.environ.get("MAILSAAS_DKIM_KEY_PATH"),
    }


def server_transport(row):
    """Per-relay transport if the SMTP server row carries credentials."""
    pw = row["password"] if "password" in row.keys() else None
    if not (row["host"] and row["username"] and pw):
        return None
    cfg = {
        "host": row["host"], "port": row["port"],
        "username": row["username"], "password": pw,
        "from": row["username"] if "@" in (row["username"] or "")
        else "no-reply@mailsaas.io",
        "tls": bool(row["use_tls"]) if "use_tls" in row.keys() else True,
    }
    # Optional per-row DKIM / reply-to columns, if present.
    for k in ("reply_to", "dkim_domain", "dkim_selector", "dkim_key",
              "dkim_key_path"):
        if k in row.keys() and row[k]:
            cfg[k] = row[k]
    return cfg


# --------------------------------------------------------------------------- #
#  DKIM
# --------------------------------------------------------------------------- #
def _load_dkim_key(cfg):
    key = cfg.get("dkim_key")
    if not key and cfg.get("dkim_key_path"):
        try:
            with open(cfg["dkim_key_path"], "rb") as fh:
                return fh.read()
        except Exception:
            return None
    if isinstance(key, str):
        key = key.encode()
    return key


def _dkim_sign(raw_bytes, cfg):
    """Return DKIM-signed bytes, or the original bytes if signing isn't
    configured/available. Never raises into the send path."""
    domain = cfg.get("dkim_domain")
    if not domain:
        return raw_bytes
    key = _load_dkim_key(cfg)
    if not key:
        return raw_bytes
    try:
        import dkim  # dkimpy (permissively licensed)
        selector = (cfg.get("dkim_selector") or "mail").encode()
        sig = dkim.sign(
            message=raw_bytes, selector=selector, domain=domain.encode(),
            privkey=key, include_headers=[b"From", b"To", b"Subject", b"Date",
                                          b"Message-ID", b"List-Unsubscribe"])
        return sig + raw_bytes
    except Exception:
        return raw_bytes  # send unsigned rather than fail


# --------------------------------------------------------------------------- #
#  Message building
# --------------------------------------------------------------------------- #
_UNSUB_RE = re.compile(r'href="(https?://[^"]+/t/u/[^"]+)"', re.IGNORECASE)


def build_message(cfg, to_addr, subject, html, from_addr=None, text=None,
                  headers=None, attachments=None):
    """Assemble a fully-formed, multipart/alternative EmailMessage with the
    headers corporate inboxes expect. Auto-derives the one-click unsubscribe
    header from the unsubscribe link already in the body."""
    msg = EmailMessage()
    sender = from_addr or cfg.get("from") or "no-reply@mailsaas.io"
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject or "(no subject)"
    msg["Date"] = formatdate(localtime=True)
    domain = sender.split("@")[-1] if "@" in sender else "mailsaas.io"
    msg["Message-ID"] = make_msgid(domain=domain)
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    msg["Precedence"] = "bulk"
    msg["Auto-Submitted"] = "auto-generated"

    # One-click unsubscribe (RFC 8058) — required for bulk Gmail/Yahoo.
    um = _UNSUB_RE.search(html or "")
    if um:
        unsub = um.group(1)
        msg["List-Unsubscribe"] = "<%s>" % unsub
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    for k, v in (headers or {}).items():
        if v:
            msg[k] = v

    # Real text part first, HTML alternative second.
    msg.set_content(text if text is not None else html_to_text(html))
    msg.add_alternative(html or "", subtype="html")

    # File attachments. Adding any attachment restructures the message into
    # multipart/mixed automatically (the EmailMessage API handles this).
    for att in (attachments or []):
        try:
            with open(att["path"], "rb") as fh:
                data = fh.read()
            mime = att.get("mime") or "application/octet-stream"
            maintype, _, subtype = mime.partition("/")
            msg.add_attachment(data, maintype=maintype or "application",
                               subtype=subtype or "octet-stream",
                               filename=att.get("filename") or "attachment")
        except Exception:
            continue
    return msg


# --------------------------------------------------------------------------- #
#  Connection handling
# --------------------------------------------------------------------------- #
def open_connection(cfg):
    """Open + authenticate one SMTP session for reuse across many messages.
    Returns a live smtplib.SMTP, or None on failure."""
    try:
        s = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
        s.ehlo()
        if cfg.get("tls", True):
            try:
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            except smtplib.SMTPException:
                pass
        if cfg.get("username") and cfg.get("password"):
            s.login(cfg["username"], cfg["password"])
        return s
    except Exception:
        return None


def smtp_send(cfg, to_addr, subject, html, from_addr=None, text=None,
              headers=None, conn=None, attachments=None):
    """Deliver one email. Returns (ok, info) — info is a short string, exactly
    as before, so existing callers are unaffected.

    New optional args:
        text     real plain-text part (defaults to auto-generated from html)
        headers  extra headers dict
        conn     a live SMTP session from open_connection() to reuse; when
                 given, the connection is NOT closed (the caller owns it)
    """
    try:
        msg = build_message(cfg, to_addr, subject, html, from_addr, text, headers,
                            attachments)
        raw = _dkim_sign(msg.as_bytes(), cfg)
        sender = (from_addr or cfg.get("from") or "no-reply@mailsaas.io")

        if conn is not None:
            conn.sendmail(sender, [to_addr], raw)
            return True, "delivered"

        s = open_connection(cfg)
        if not s:
            return False, "connect failed"
        try:
            s.sendmail(sender, [to_addr], raw)
        finally:
            try:
                s.quit()
            except Exception:
                pass
        return True, "delivered"
    except Exception as e:  # noqa: BLE001
        return False, "%s: %s" % (type(e).__name__, e)


# --------------------------------------------------------------------------- #
#  Bounce classification
# --------------------------------------------------------------------------- #
_HARD_CODES = {550, 551, 553, 554, 501, 511}
_SOFT_CODES = {421, 450, 451, 452, 471}
_HARD_HINTS = ("no such user", "user unknown", "does not exist",
               "mailbox unavailable", "invalid recipient", "no mailbox",
               "recipient rejected", "address rejected")
_SOFT_HINTS = ("greylist", "try again", "temporarily", "rate limit",
               "quota", "mailbox full", "over quota", "deferred", "timeout",
               "connection")


def classify_failure(info):
    """Turn the info string from smtp_send (or any SMTP error text) into a
    decision: hard (permanent -> suppress) vs soft (transient -> retry).

    Returns {'type': 'hard'|'soft', 'code': int|None, 'suppress': bool}.
    """
    text = (info or "").lower()
    code = None
    m = re.search(r"\b([45]\d\d)\b", text)
    if m:
        code = int(m.group(1))

    if code in _HARD_CODES or any(h in text for h in _HARD_HINTS):
        return {"type": "hard", "code": code, "suppress": True}
    if code in _SOFT_CODES or any(h in text for h in _SOFT_HINTS):
        return {"type": "soft", "code": code, "suppress": False}
    if code and 500 <= code < 600:
        return {"type": "hard", "code": code, "suppress": True}
    return {"type": "soft", "code": code, "suppress": False}


# A 1x1 transparent GIF returned by the open-tracking pixel.
PIXEL_GIF = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
    0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x21, 0xF9, 0x04, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3B,
])
