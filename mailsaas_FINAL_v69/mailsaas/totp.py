"""
RFC 6238 TOTP — implemented with the Python standard library only.

No external dependency (works with Google Authenticator, Authy, 1Password, …).
Used by the real two-factor-authentication flow.
"""
import hmac
import time
import base64
import struct
import hashlib
import secrets
from urllib.parse import quote


def new_secret():
    """Return a fresh base32 secret (no padding) suitable for authenticator apps."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _hotp(secret_b32, counter, digits=6):
    # Re-pad base32 for decoding.
    pad = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = base64.b32decode(secret_b32.upper() + pad)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_now(secret_b32, step=30, digits=6, at=None):
    counter = int((at if at is not None else time.time()) // step)
    return _hotp(secret_b32, counter, digits)


def verify(secret_b32, code, step=30, digits=6, window=1):
    """Validate a user-supplied code, allowing +/- `window` time steps for drift."""
    if not secret_b32 or not code:
        return False
    code = str(code).strip().replace(" ", "")
    if not code.isdigit():
        return False
    now = time.time()
    for drift in range(-window, window + 1):
        counter = int(now // step) + drift
        if hmac.compare_digest(_hotp(secret_b32, counter, digits), code):
            return True
    return False


def provisioning_uri(secret_b32, account_name, issuer="MailSaaS"):
    """otpauth:// URI you can render as a QR code."""
    label = quote(f"{issuer}:{account_name}")
    return (f"otpauth://totp/{label}?secret={secret_b32}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30")
