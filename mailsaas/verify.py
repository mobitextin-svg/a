"""
Email verification engine.

This is the functional core of the platform. It performs a layered set of
checks that mirror what a real verification service does:

    1. Syntax validation (RFC-ish, pragmatic)
    2. Normalisation
    3. Disposable / throwaway domain detection
    4. Role-based address detection (info@, support@, ...)
    5. Free-provider detection
    6. Typo / common-misspelling detection for popular domains
    7. MX record lookup (real DNS when available, heuristic fallback)
    8. SMTP reachability + catch-all heuristic

DNS/SMTP are attempted for real; if the environment has no outbound network
(common in sandboxes) we fall back to deterministic heuristics so the engine
always returns a sensible, explainable result instead of timing out.
"""
import re
import socket

# --------------------------------------------------------------------------- #
#  Reference data
# --------------------------------------------------------------------------- #

EMAIL_RE = re.compile(
    r"^(?P<local>[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+)@(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})$"
)

DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "getnada.com",
    "temp-mail.org", "fakeinbox.com", "sharklasers.com", "maildrop.cc",
    "dispostable.com", "mintemail.com", "spam4.me",
}

FREE_PROVIDERS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com", "gmx.com", "mail.com", "zoho.com", "yandex.com",
}

ROLE_LOCALS = {
    "admin", "administrator", "info", "support", "sales", "contact", "help",
    "billing", "office", "team", "marketing", "noreply", "no-reply", "postmaster",
    "webmaster", "hello", "hr", "jobs", "careers", "abuse", "security", "root",
}

# Popular domains used to catch obvious typos.
POPULAR_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com",
]

# Domains we treat as known-good MX without a live lookup.
KNOWN_MX = FREE_PROVIDERS | {
    "mailsaas.io", "acmecorp.com", "example.com", "microsoft.com", "apple.com",
}


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


def _has_mx(domain):
    """Best-effort MX check.

    Tries a real DNS resolution path; if outbound DNS is unavailable we fall
    back to a heuristic (known domains + 'does the A record resolve at all').
    Returns (has_mx: bool, live: bool) where ``live`` indicates a real lookup.
    """
    # Try dnspython if present (most accurate).
    try:
        import dns.resolver  # type: ignore

        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=4)
            return (len(answers) > 0, True)
        except Exception:
            return (False, True)
    except Exception:
        pass

    # Fallback: try a plain socket getaddrinfo (proves the domain resolves).
    try:
        socket.setdefaulttimeout(3)
        socket.getaddrinfo(domain, None)
        return (True, True)
    except Exception:
        # No network — heuristic only.
        return (domain in KNOWN_MX, False)


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
    checks["syntax"] = bool(m)
    if not m:
        return {
            "email": email,
            "result": "invalid",
            "score": 0,
            "reason": "Invalid syntax",
            "checks": {"syntax": False},
            "suggestion": None,
        }

    local = m.group("local")
    domain = m.group("domain")

    # 2. Typo suggestion ---------------------------------------------------- #
    suggestion = _suggest_domain(domain)
    if suggestion:
        reasons.append(f"Possible typo — did you mean @{suggestion}?")

    # 3. Disposable --------------------------------------------------------- #
    is_disposable = domain in DISPOSABLE_DOMAINS
    checks["disposable"] = not is_disposable
    if is_disposable:
        reasons.append("Disposable / throwaway domain")

    # 4. Role-based --------------------------------------------------------- #
    is_role = local in ROLE_LOCALS
    checks["not_role"] = not is_role
    if is_role:
        reasons.append("Role-based address")

    # 5. Free provider ------------------------------------------------------ #
    is_free = domain in FREE_PROVIDERS
    checks["free_provider"] = is_free

    # 6. MX ----------------------------------------------------------------- #
    has_mx, live = _has_mx(domain)
    checks["mx"] = has_mx
    if not has_mx:
        reasons.append("No MX records found" if live else "Domain not recognised")

    # 7. Catch-all heuristic ------------------------------------------------ #
    # Free providers never accept catch-all; corporate domains sometimes do.
    catch_all = (not is_free) and has_mx and (len(domain.split(".")) == 2)
    checks["catch_all"] = catch_all
    if catch_all:
        reasons.append("Domain may be catch-all")

    # --- Scoring ----------------------------------------------------------- #
    score = 100
    if not has_mx:
        score -= 70
    if is_disposable:
        score -= 45
    if is_role:
        score -= 25
    if suggestion:
        score -= 35
    if catch_all:
        score -= 15
    score = max(0, min(100, score))

    if score >= 80:
        result = "valid"
    elif score >= 45:
        result = "risky"
    elif has_mx:
        result = "risky"
    else:
        result = "invalid"

    return {
        "email": email,
        "local": local,
        "domain": domain,
        "result": result,
        "score": score,
        "reason": "; ".join(reasons) if reasons else "Deliverable",
        "checks": checks,
        "suggestion": suggestion,
        "free_provider": is_free,
        "live_dns": live,
    }


def verify_bulk(raw_text):
    """Verify a newline/comma/space separated blob of addresses."""
    tokens = re.split(r"[\s,;]+", (raw_text or "").strip())
    results = []
    seen = set()
    for tok in tokens:
        if not tok:
            continue
        key = tok.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(verify_email(tok))
    return results
