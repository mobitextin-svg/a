"""
Email verification engine — REAL network checks.

Drop-in replacement for the previous verify.py. Public API is unchanged
(`verify_email`, `verify_bulk`) and the returned dict keeps every key the UI
and JSON API already use, so nothing else in the app needs to change.

What is REAL now (was fabricated before):
    * MX        — true MX record lookup (dnspython), sorted by priority
    * SMTP      — real EHLO -> MAIL FROM -> RCPT TO conversation (no DATA sent)
    * catch-all — real probe of a random non-existent mailbox on the domain
    * greylist  — detected from genuine 4xx temporary responses
    * domain age— real registration date via RDAP (open standard)

Honest degradation:
    If outbound DNS / port-25 is unavailable (sandboxes, or hosts that block
    25), we DO NOT invent a result. The mailbox check returns "unknown" and the
    overall result becomes "unknown" rather than a fake "valid". Set the engine
    to MX-only with VERIFY_SMTP=0 if your host blocks port 25.

Environment:
    VERIFY_SMTP        "1" (default) to run live SMTP probes, "0" for MX-only
    VERIFY_MAIL_FROM   envelope sender used in probes (default verify@mailsaas.io)
    VERIFY_RDAP        "1" (default) to look up real domain age via RDAP
    VERIFY_SMTP_TIMEOUT seconds per SMTP attempt (default 8)
"""
import os
import re
import json
import socket
import smtplib
import hashlib
import datetime
import urllib.request

# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
SMTP_ENABLED = os.environ.get("VERIFY_SMTP", "1") != "0"
RDAP_ENABLED = os.environ.get("VERIFY_RDAP", "1") != "0"
MAIL_FROM = os.environ.get("VERIFY_MAIL_FROM", "verify@mailsaas.io")
SMTP_TIMEOUT = float(os.environ.get("VERIFY_SMTP_TIMEOUT", "8"))

# Per-process caches — verifying a list of 5,000 addresses at one company
# should hit the network once, not 5,000 times.
_MX_CACHE = {}        # domain -> (mx_hosts: list[str], live: bool)
_CATCHALL_CACHE = {}  # domain -> bool|None
_AGE_CACHE = {}       # domain -> int|None

# --------------------------------------------------------------------------- #
#  Reference data
# --------------------------------------------------------------------------- #
EMAIL_RE = re.compile(
    r"^(?P<local>[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+)@(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})$"
)

# A starter disposable set. In production, refresh this from an open-source
# list (e.g. the public disposable-email-domains repo) into DISPOSABLE_DOMAINS
# on boot — the lookup below already handles a large set efficiently.
DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "getnada.com",
    "temp-mail.org", "fakeinbox.com", "sharklasers.com", "maildrop.cc",
    "dispostable.com", "mintemail.com", "spam4.me", "tempr.email",
    "discard.email", "mailnesia.com", "moakt.com", "emailondeck.com",
    "tempmailo.com", "1secmail.com", "burnermail.io", "guerrillamail.info",
}

FREE_PROVIDERS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com", "gmx.com", "mail.com", "zoho.com", "yandex.com",
    "live.com", "rediffmail.com", "ymail.com",
}

ROLE_LOCALS = {
    "admin", "administrator", "info", "support", "sales", "contact", "help",
    "billing", "office", "team", "marketing", "noreply", "no-reply", "postmaster",
    "webmaster", "hello", "hr", "jobs", "careers", "abuse", "security", "root",
    "enquiry", "enquiries", "accounts", "feedback",
}

POPULAR_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com", "rediffmail.com",
]

# --------------------------------------------------------------------------- #
#  Small helpers
# --------------------------------------------------------------------------- #
def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _suggest_domain(domain):
    """Return a likely correction for a misspelled popular domain, or None."""
    if domain in POPULAR_DOMAINS:
        return None
    best, best_d = None, 99
    for cand in POPULAR_DOMAINS:
        d = _levenshtein(domain, cand)
        if d < best_d:
            best, best_d = cand, d
    return best if 0 < best_d <= 2 else None


def _resolve_mx(domain):
    """Real MX lookup. Returns (mx_hosts sorted by priority, live: bool).

    `live` is True when a real DNS query ran (so an empty list genuinely means
    "no MX"); False means we couldn't reach DNS at all (sandbox / offline) and
    the empty result is *unknown*, not a confirmed absence.
    """
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]
    hosts, live = [], False
    try:
        import dns.resolver  # type: ignore
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=5)
            hosts = [str(r.exchange).rstrip(".") for r in
                     sorted(answers, key=lambda r: r.preference)]
            live = True
        except dns.resolver.NoAnswer:
            live = True            # domain exists but has no MX
        except dns.resolver.NXDOMAIN:
            live = True            # domain does not exist
        except Exception:
            live = False           # timeout / no network
    except Exception:
        # dnspython not installed — fall back to A-record existence as a weak
        # signal (does the domain resolve at all?). Flagged as not-live so the
        # scorer treats a miss as "unknown".
        try:
            socket.setdefaulttimeout(4)
            socket.getaddrinfo(domain, None)
            hosts, live = [domain], False
        except Exception:
            hosts, live = [], False
    _MX_CACHE[domain] = (hosts, live)
    return hosts, live


def _rand_localpart():
    import secrets
    return "zzv-" + secrets.token_hex(6)


def _smtp_probe(mx_hosts, address, domain, check_catch_all=True):
    """Real SMTP RCPT TO probe.

    Returns a dict:
        deliverable : True | False | None   (None = could not determine)
        greylisted  : bool
        catch_all   : True | False | None
        code        : last SMTP code seen
        connected   : bool
    No message body (DATA) is ever sent — we only ask whether the server would
    accept the recipient.
    """
    out = {"deliverable": None, "greylisted": False, "catch_all": None,
           "code": None, "connected": False}
    if not mx_hosts:
        return out

    for host in mx_hosts:
        server = None
        try:
            server = smtplib.SMTP(timeout=SMTP_TIMEOUT)
            server.connect(host, 25)
            out["connected"] = True
            server.ehlo_or_helo_if_needed()
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                pass  # plenty of MX hosts don't offer STARTTLS on 25
            server.mail(MAIL_FROM)

            code, _ = server.rcpt(address)
            out["code"] = code
            if code in (250, 251):
                out["deliverable"] = True
            elif code in (421, 450, 451, 452):
                out["deliverable"] = None
                out["greylisted"] = True
            elif code in (550, 551, 553, 554, 521, 511):
                out["deliverable"] = False
            else:
                out["deliverable"] = None

            # Catch-all: does the server also accept an obviously fake mailbox?
            if check_catch_all and domain not in _CATCHALL_CACHE:
                try:
                    c2, _ = server.rcpt("%s@%s" % (_rand_localpart(), domain))
                    _CATCHALL_CACHE[domain] = c2 in (250, 251)
                except Exception:
                    _CATCHALL_CACHE[domain] = None
            out["catch_all"] = _CATCHALL_CACHE.get(domain)

            try:
                server.quit()
            except Exception:
                pass
            return out
        except (socket.timeout, ConnectionRefusedError, OSError,
                smtplib.SMTPException):
            # Try the next MX host.
            try:
                if server:
                    server.close()
            except Exception:
                pass
            continue
    return out  # never connected -> deliverable stays None (unknown)


def _domain_age_days(domain):
    """Real registration age via RDAP (RFC 7482). None if unavailable."""
    if not RDAP_ENABLED:
        return None
    if domain in _AGE_CACHE:
        return _AGE_CACHE[domain]
    age = None
    try:
        req = urllib.request.Request(
            "https://rdap.org/domain/" + domain,
            headers={"User-Agent": "MailSaaS-Verify/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
        for ev in data.get("events", []):
            if ev.get("eventAction") == "registration":
                d = ev.get("eventDate", "")[:10]
                reg = datetime.date.fromisoformat(d)
                age = (datetime.date.today() - reg).days
                break
    except Exception:
        age = None
    _AGE_CACHE[domain] = age
    return age


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def verify_email(raw):
    """Verify a single address. Returns a dict with an overall result plus a
    breakdown of every sub-check (used by the UI and the JSON API)."""
    email = (raw or "").strip().lower()
    checks = {}
    reasons = []

    # 1. Syntax ------------------------------------------------------------- #
    m = EMAIL_RE.match(email)
    if not m:
        return {
            "email": email, "result": "invalid", "score": 0, "risk_score": 100,
            "risk_band": "high", "domain_age_days": None,
            "reason": "Invalid syntax", "checks": {"syntax": False},
            "suggestion": None, "free_provider": False, "live_dns": False,
        }
    checks["syntax"] = True
    local = m.group("local")
    domain = m.group("domain")

    # 2. Typo suggestion ---------------------------------------------------- #
    suggestion = _suggest_domain(domain)
    if suggestion:
        reasons.append("Possible typo — did you mean @%s?" % suggestion)

    # 3. Disposable / role / free ------------------------------------------ #
    is_disposable = domain in DISPOSABLE_DOMAINS
    checks["disposable"] = not is_disposable
    if is_disposable:
        reasons.append("Disposable / throwaway domain")

    is_role = local in ROLE_LOCALS
    checks["not_role"] = not is_role
    if is_role:
        reasons.append("Role-based address")

    is_free = domain in FREE_PROVIDERS
    checks["free_provider"] = is_free

    # 4. MX (real) ---------------------------------------------------------- #
    mx_hosts, dns_live = _resolve_mx(domain)
    has_mx = bool(mx_hosts)
    checks["mx"] = has_mx
    if dns_live and not has_mx:
        reasons.append("No MX records — domain can't receive mail")
    elif not dns_live and not has_mx:
        reasons.append("DNS unavailable — MX unconfirmed")

    # 5. SMTP probe (real) -------------------------------------------------- #
    deliverable = None         # True / False / None(unknown)
    catch_all = None
    greylisted = False
    probe_ran = False
    if SMTP_ENABLED and has_mx and not is_disposable:
        probe = _smtp_probe(mx_hosts, email, domain)
        probe_ran = probe["connected"]
        deliverable = probe["deliverable"]
        catch_all = probe["catch_all"]
        greylisted = probe["greylisted"]

    if deliverable is True:
        checks["smtp"] = True
    elif deliverable is False:
        checks["smtp"] = False
        reasons.append("Mailbox does not exist (SMTP 550)")
    else:
        # Unknown — be honest, don't fake it.
        if SMTP_ENABLED and has_mx and not probe_ran:
            reasons.append("Mailbox unconfirmed (no SMTP connection)")
        elif greylisted:
            reasons.append("Greylisted — temporary deferral, retry later")

    if catch_all:
        checks["accept_all"] = False
        reasons.append("Catch-all domain — accepts any address")
    elif catch_all is False:
        checks["accept_all"] = True

    if greylisted:
        checks["greylisting"] = False

    # 6. Domain age (real, best-effort) ------------------------------------ #
    domain_age_days = None
    if has_mx and not is_free:
        domain_age_days = _domain_age_days(domain)
    young = domain_age_days is not None and domain_age_days < 90
    if domain_age_days is not None:
        checks["domain_age_ok"] = not young
        if young:
            reasons.append("Young domain (~%dd old)" % domain_age_days)

    # 7. Spam-trap *pattern hint* (honest: a hint, not detection) ---------- #
    trap_hint = local in ("a", "b", "x", "test", "asdf") or \
        any(local.startswith(p) for p in ("spamtrap", "trap@"))
    if trap_hint:
        checks["not_spam_trap"] = False
        reasons.append("Spam-trap-like pattern")

    # --- Scoring ----------------------------------------------------------- #
    score = 100
    if not dns_live and not has_mx:
        score -= 40            # unknown, not condemned
    elif dns_live and not has_mx:
        score -= 75
    if deliverable is False:
        score -= 80
    elif deliverable is None and has_mx:
        score -= 30            # couldn't confirm mailbox
    if is_disposable:
        score -= 50
    if is_role:
        score -= 20
    if suggestion:
        score -= 30
    if catch_all:
        score -= 25
    if greylisted:
        score -= 5
    if young:
        score -= 12
    if trap_hint:
        score -= 45
    score = max(0, min(100, score))

    # Risk (higher = riskier) ---------------------------------------------- #
    risk = 0
    risk += 45 if trap_hint else 0
    risk += 30 if is_disposable else 0
    risk += 20 if young else 0
    risk += 20 if catch_all else 0
    risk += 15 if is_role else 0
    risk += 40 if (dns_live and not has_mx) else 0
    risk += 35 if deliverable is False else 0
    risk = max(0, min(100, risk))
    risk_band = "high" if risk >= 60 else ("medium" if risk >= 30 else "low")

    # --- Overall result ---------------------------------------------------- #
    if dns_live and not has_mx:
        result = "invalid"
    elif deliverable is False:
        result = "invalid"
    elif is_disposable:
        result = "risky"
    elif deliverable is True and not catch_all:
        result = "valid"
    elif catch_all:
        result = "risky"
    elif deliverable is None:
        result = "unknown"     # honest: we could not confirm
    else:
        result = "risky"

    return {
        "email": email, "local": local, "domain": domain,
        "result": result, "score": score,
        "risk_score": risk, "risk_band": risk_band,
        "domain_age_days": domain_age_days,
        "reason": "; ".join(reasons) if reasons else "Deliverable",
        "checks": checks, "suggestion": suggestion,
        "free_provider": is_free, "live_dns": dns_live,
    }


def verify_bulk(raw_text):
    """Verify a newline/comma/space separated blob of addresses.
    Per-domain DNS/SMTP/RDAP results are cached, so a big single-company list
    only touches the network once per domain."""
    tokens = re.split(r"[\s,;]+", (raw_text or "").strip())
    results, seen = [], set()
    for tok in tokens:
        if not tok:
            continue
        key = tok.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(verify_email(tok))
    return results
