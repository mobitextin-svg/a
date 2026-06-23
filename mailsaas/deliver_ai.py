"""
Deliverability intelligence — predictive scoring + AI recommendations.

Pure, unit-testable functions over a `signals` dict assembled from the
account's real data (reputation, bounce/complaint rates, warm-up status, list
hygiene, domain authentication, blacklist status). No external calls — this is
the rules/ML layer that turns raw signals into a forecast and an action list.
"""


def predict_deliverability(s):
    """Predict an inbox-placement score (0–100) with a factor breakdown.
    `s` is a dict of real signals; each factor shows its impact on the score."""
    score = 100.0
    factors = []

    def hit(name, delta, note):
        nonlocal score
        score += delta
        factors.append({"name": name, "impact": round(delta, 1), "note": note})

    rep = s.get("reputation", 85)
    hit("Domain/IP reputation", (rep - 85) * 0.4,
        f"Reputation {rep}/100")

    br = s.get("bounce_rate", 0)
    if br > 5:
        hit("Bounce rate", -min(25, br * 2), f"{br:.1f}% — high")
    elif br > 2:
        hit("Bounce rate", -8, f"{br:.1f}% — elevated")
    else:
        hit("Bounce rate", 3, f"{br:.1f}% — healthy")

    cr = s.get("complaint_rate", 0)
    if cr > 0.3:
        hit("Complaint rate", -min(30, cr * 40), f"{cr:.2f}% — above ISP threshold")
    elif cr > 0.1:
        hit("Complaint rate", -10, f"{cr:.2f}% — watch")
    else:
        hit("Complaint rate", 2, f"{cr:.2f}% — good")

    auth = s.get("auth_ok", True)
    hit("SPF/DKIM/DMARC", 0 if auth else -18,
        "Fully authenticated" if auth else "Authentication incomplete")

    if s.get("warmup_pending"):
        hit("Warm-up", -8, "Relays still warming")

    up = s.get("unverified_pct", 0)
    if up > 30:
        hit("List quality", -12, f"{up:.0f}% unverified addresses")
    elif up > 10:
        hit("List quality", -5, f"{up:.0f}% unverified")

    if s.get("blacklisted"):
        hit("Blacklist", -25, "Listed on a blacklist")

    score = max(0, min(100, score))
    band = ("Excellent" if score >= 90 else "Good" if score >= 75
            else "Fair" if score >= 55 else "Poor")
    factors.sort(key=lambda f: f["impact"])
    return {"score": round(score, 1), "band": band, "factors": factors}


def recommendations(s):
    """Prioritised, actionable recommendations (critical → warning → tip)."""
    recs = []

    def add(sev, title, detail):
        recs.append({"severity": sev, "title": title, "detail": detail})

    if s.get("blacklisted"):
        add("critical", "You're on a blacklist",
            "Request delisting and pause sends from the affected IP until clean.")
    if s.get("complaint_rate", 0) > 0.3:
        add("critical", "Complaint rate above ISP threshold",
            "Tighten opt-in, remove unengaged contacts, and slow your send rate.")
    if not s.get("auth_ok", True):
        add("critical", "Finish email authentication",
            "Publish SPF, DKIM and a DMARC policy — unauthenticated mail gets filtered.")
    if s.get("bounce_rate", 0) > 2:
        add("warning", "Reduce your bounce rate",
            "Run Email Verification on your list and enable Automatic List Cleaning.")
    if s.get("unverified_pct", 0) > 10:
        add("warning", "Verify your contacts",
            f"{s['unverified_pct']:.0f}% of contacts are unverified — clean before sending.")
    if s.get("warmup_pending"):
        add("warning", "Keep warming your IPs",
            "Stay within the daily warm-up plan to keep building reputation.")
    if s.get("role_pct", 0) > 5:
        add("tip", "Trim role addresses",
            "info@/support@ addresses hurt engagement — consider excluding them.")
    if s.get("reputation", 85) < 80:
        add("tip", "Improve sender reputation",
            "Send to engaged users first; consistent volume rebuilds reputation.")
    if not recs:
        add("tip", "Deliverability looks great",
            "Maintain list hygiene and consistent sending to stay in the inbox.")
    order = {"critical": 0, "warning": 1, "tip": 2}
    recs.sort(key=lambda r: order[r["severity"]])
    return recs
