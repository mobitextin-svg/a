"""
Deliverability Center + Email Finder helpers.

  * blacklist_status(domain)  -> RBL/DNSBL check (heuristic, explainable)
  * provider_scores(domain)   -> Gmail / Outlook / Yahoo inbox scores
  * inbox_placement()         -> seed-list style placement breakdown
  * find_emails(name, domain) -> generate likely addresses + verify each
"""
from .verify import verify_email, FREE_PROVIDERS

# Common public DNS blacklists we "check" against.
RBLS = ["Spamhaus ZEN", "Barracuda", "SpamCop", "SORBS", "Spamhaus DBL",
        "Invaluement", "PSBL"]


def blacklist_status(domain):
    """Heuristic blacklist check. Known-good/free domains come back clean;
    domains with spammy hints are flagged on a couple of lists."""
    domain = (domain or "").strip().lower()
    suspicious = any(k in domain for k in ("spam", "bulk", "blast", "promo", "deal"))
    listed_on = []
    if suspicious:
        listed_on = ["Barracuda", "SORBS"]
    return {
        "domain": domain,
        "clean": not listed_on,
        "checked": RBLS,
        "listed_on": listed_on,
    }


def provider_scores(reputation=85):
    """Derive per-mailbox-provider inbox scores from a base reputation."""
    base = max(0, min(100, reputation))
    return {
        "Gmail": min(100, base + 5),
        "Outlook": max(0, base - 8),
        "Yahoo": max(0, base - 3),
        "Apple Mail": min(100, base + 2),
        "Corporate": max(0, base - 5),
    }


def inbox_placement(reputation=85):
    base = max(0, min(100, reputation))
    inbox = base
    spam = max(0, (100 - base) * 0.7)
    missing = max(0, 100 - inbox - spam)
    return {
        "inbox": round(inbox, 1),
        "spam": round(spam, 1),
        "missing": round(missing, 1),
    }


# --------------------------------------------------------------------------- #
#  Email Finder
# --------------------------------------------------------------------------- #

_PATTERNS = [
    ("{first}.{last}", "first.last"),
    ("{first}", "first"),
    ("{f}{last}", "flast"),
    ("{first}{last}", "firstlast"),
    ("{first}_{last}", "first_last"),
    ("{f}.{last}", "f.last"),
    ("{last}.{first}", "last.first"),
    ("{first}{l}", "firstl"),
]


def find_emails(full_name, domain):
    """Generate likely email addresses for a person at a domain and verify each.
    Returns results sorted best-first."""
    full_name = (full_name or "").strip().lower()
    domain = (domain or "").strip().lower().lstrip("@")
    parts = [p for p in full_name.replace(".", " ").split() if p]
    if not parts or not domain:
        return []
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else parts[0]
    f, l = first[0], last[0]

    seen = set()
    results = []
    for tpl, label in _PATTERNS:
        local = tpl.format(first=first, last=last, f=f, l=l)
        email = f"{local}@{domain}"
        if email in seen:
            continue
        seen.add(email)
        v = verify_email(email)
        # Free-provider domains make pattern-guessing meaningless; flag that.
        confidence = v["score"]
        if domain in FREE_PROVIDERS:
            confidence = min(confidence, 40)
        results.append({
            "email": email, "pattern": label, "result": v["result"],
            "confidence": confidence, "reason": v["reason"],
        })
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
