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


# --------------------------------------------------------------------------- #
#  Content-level inbox-placement score + one-click optimizer.
#  These look at the *email itself* (subject + HTML body), independent of the
#  account signals above. A perfect email scores 100%.
# --------------------------------------------------------------------------- #
import re as _re

SPAM_WORDS = [
    "free", "winner", "congratulations", "guaranteed", "risk-free", "click here",
    "buy now", "limited time", "act now", "cash", "viagra", "lottery", "prize",
    "urgent", "100% free", "no cost", "cheap", "earn money", "make money",
    "double your", "miracle", "weight loss", "$$$", "best price",
]
# Softer replacements used by the optimizer.
SPAM_FIX = {
    "free": "complimentary", "winner": "selected", "congratulations": "good news",
    "guaranteed": "assured", "risk-free": "no-obligation", "click here": "see details",
    "buy now": "explore", "limited time": "for a short period", "act now": "learn more",
    "cash": "savings", "100% free": "included", "no cost": "included",
    "cheap": "affordable", "earn money": "grow income", "make money": "grow income",
    "double your": "increase your", "miracle": "effective", "urgent": "important",
    "best price": "great value", "$$$": "great value", "prize": "reward",
    "lottery": "draw", "weight loss": "wellness", "viagra": "product",
    "congratulations": "good news", "guaranteed": "assured", "no cost": "included",
}


def _text_of(html):
    return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html or "")).strip()


def inbox_score(subject, body):
    """Predict inbox vs spam placement for one email. Returns score 0–100,
    a band, and a factor list (each with pass/fail + how to fix)."""
    subject = subject or ""
    body = body or ""
    text = _text_of(body)
    low = (subject + " " + body).lower()
    factors = []

    def check(label, ok, weight, fix):
        factors.append({"label": label, "ok": bool(ok), "weight": weight,
                        "fix": fix})

    has_unsub = ("{{unsubscribe_url}}" in body or "/t/u/" in body
                 or "unsubscribe" in low)
    has_view = "{{view_in_browser_url}}" in body or "view in browser" in low
    letters = [c for c in subject if c.isalpha()]
    all_caps = len(letters) >= 6 and all(c.isupper() for c in letters)
    bad_punct = bool(_re.search(r"[!]{2,}|[?]{2,}|\${2,}|%{2,}", subject)) \
        or subject.count("!") > 1
    spam_hits = [w for w in SPAM_WORDS if w in low]
    link_count = len(_re.findall(r"href=", body, _re.IGNORECASE))

    check("Unsubscribe link", has_unsub, 15,
          "Add {{unsubscribe_url}} (required by law & ISPs).")
    check("View-in-browser link", has_view, 8,
          "Add {{view_in_browser_url}} so the email always renders.")
    check("Personalised ({{name}})", "{{name}}" in body, 7,
          "Use {{name}} so it doesn't look like bulk mail.")
    check("Subject present", bool(subject.strip()), 6, "Add a subject line.")
    check("Subject not ALL CAPS", not all_caps, 8,
          "Avoid all-capitals subjects — a classic spam trigger.")
    check("Clean subject punctuation", not bad_punct, 8,
          "Remove repeated !!! / $$$ from the subject.")
    check("No spam-trigger words", not spam_hits, 16,
          "Replace words like " + (", ".join(spam_hits[:3]) or "free/winner/…") + ".")
    check("Has real text content", len(text) >= 80, 10,
          "Add text — image-only emails get filtered.")
    check("Has a footer/address", ("©" in body or "rights reserved" in low
          or "unsubscribe" in low), 6, "Add a footer with your company details.")
    check("Reasonable link count", link_count <= 12, 6,
          "Too many links looks spammy — trim them.")
    check("No generic 'click here'", "click here" not in low, 5,
          "Use descriptive link text instead of 'click here'.")
    check("Good body length", 80 <= len(text) <= 6000, 5,
          "Keep the email a sensible length.")

    score = sum(f["weight"] for f in factors if f["ok"])
    band = ("Inbox" if score >= 90 else "Mostly inbox" if score >= 75
            else "At risk" if score >= 55 else "Likely spam")
    issues = [f for f in factors if not f["ok"]]
    return {"score": score, "band": band, "factors": factors, "issues": issues}


# --------------------------------------------------------------------------- #
#  Detailed content analysis — the granular metrics shown on the Inbox
#  Analysis report (spam words, ALL-CAPS, emoji, image/text ratio, broken
#  links, unsubscribe, physical address, HTML validity). Real checks over the
#  actual subject + HTML body; no external calls.
# --------------------------------------------------------------------------- #
_EMOJI = _re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF←-⇿⬀-⯿]")


def content_analysis(subject, body):
    """Return a granular breakdown of an email's content for the report.
    Each entry is {label, value, ok, hint} so the template can render rows
    with a green/red status and a short explanation."""
    subject = subject or ""
    body = body or ""
    text = _text_of(body)
    low = (subject + " " + body).lower()
    rows = []

    def add(label, value, ok, hint=""):
        rows.append({"label": label, "value": value, "ok": bool(ok), "hint": hint})

    # Spam words.
    spam_hits = [w for w in SPAM_WORDS if w in low]
    add("Spam words", (", ".join(spam_hits[:4]) + ("…" if len(spam_hits) > 4 else ""))
        if spam_hits else "None found", not spam_hits,
        "Replace trigger words with softer wording.")

    # ALL CAPS subject.
    letters = [c for c in subject if c.isalpha()]
    all_caps = len(letters) >= 6 and all(c.isupper() for c in letters)
    add("ALL CAPS subject", "Yes" if all_caps else "No", not all_caps,
        "Avoid all-capital subject lines — a classic spam trigger.")

    # Emoji count.
    emojis = _EMOJI.findall(subject + " " + text)
    add("Emoji count", str(len(emojis)), len(emojis) <= 3,
        "Keep emojis to 3 or fewer; too many looks promotional.")

    # Image / text ratio.
    img_count = len(_re.findall(r"<img\b", body, _re.IGNORECASE))
    text_len = len(text)
    if img_count == 0:
        ratio_ok, ratio_val = text_len >= 1, ("0 images" if text_len else "empty")
    else:
        per_img = text_len / img_count
        ratio_ok = per_img >= 40
        ratio_val = f"{img_count} image(s), {text_len} chars"
    add("Image / text ratio", ratio_val, ratio_ok,
        "Add more text — image-heavy emails get filtered.")

    # Broken / empty links.
    hrefs = _re.findall(r'href\s*=\s*["\']?([^"\'>\s]*)', body, _re.IGNORECASE)
    broken = [h for h in hrefs if h.strip() in ("", "#") or h.strip().startswith("javascript:")]
    add("Broken links", f"{len(broken)} of {len(hrefs)}" if hrefs else "No links",
        not broken, "Fix empty (#) or javascript: links before sending.")

    # Unsubscribe link.
    has_unsub = ("{{unsubscribe_url}}" in body or "/t/u/" in body or "unsubscribe" in low)
    add("Unsubscribe link", "Present" if has_unsub else "Missing", has_unsub,
        "Add {{unsubscribe_url}} — required by law and ISPs.")

    # Physical mailing address (CAN-SPAM). Heuristic.
    has_addr = bool(_re.search(r"\b\d{1,5}\s+\w+(\s+\w+){0,3}\s+(st|street|ave|avenue|"
                               r"rd|road|blvd|lane|ln|drive|dr|suite|ste|p\.?o\.?\s*box)\b",
                               low) or _re.search(r"\b\d{5}(-\d{4})?\b", text)
                    or "rights reserved" in low)
    add("Physical address", "Found" if has_addr else "Missing", has_addr,
        "Add your company's postal address in the footer (CAN-SPAM).")

    # Basic HTML validity — tag balance heuristic for block tags.
    html_ok, html_note = _html_balanced(body)
    add("HTML validation", "Valid" if html_ok else html_note, html_ok,
        "Close all open tags — broken HTML renders badly and looks spammy.")

    issues = [r for r in rows if not r["ok"]]
    return {"rows": rows, "issues": issues,
            "spam_words": spam_hits, "emoji_count": len(emojis),
            "image_count": img_count, "broken_links": len(broken)}


def _html_balanced(html):
    """Cheap well-formedness check: every opened block tag is closed."""
    if not html or "<" not in html:
        return True, "No HTML"
    track = ("div", "table", "tr", "td", "p", "span", "a", "ul", "ol", "li",
             "h1", "h2", "h3", "body", "html", "head", "section")
    opens = _re.findall(r"<\s*([a-zA-Z0-9]+)", html)
    closes = _re.findall(r"<\s*/\s*([a-zA-Z0-9]+)", html)
    for tag in track:
        o = sum(1 for t in opens if t.lower() == tag)
        c = sum(1 for t in closes if t.lower() == tag)
        if o > c:
            return False, f"Unclosed <{tag}> ({o - c})"
    return True, "Valid"


def provider_inbox(account_provider_scores, content_score):
    """Blend per-provider account reputation with the email's content score
    into a per-provider inbox-probability the report shows (Gmail/Outlook/…)."""
    blended = {}
    for prov, base in account_provider_scores.items():
        blended[prov] = max(0, min(100, round(0.6 * base + 0.4 * content_score)))
    return blended


def send_readiness(content_score, account_score):
    """Merge the email-content inbox score with the account-level
    deliverability score into a single 'ready to send' number (0–100).

    Content (subject/body/footer) is what one click can fix; account signals
    (reputation, auth, warm-up, list quality) need ongoing work — so the blend
    leans slightly toward account health.
    """
    content_score = max(0, min(100, content_score))
    account_score = max(0, min(100, account_score))
    overall = round(0.45 * content_score + 0.55 * account_score)
    if overall >= 85:
        verdict, level = "Ready to send", "good"
    elif overall >= 65:
        verdict, level = "Send with caution", "warn"
    else:
        verdict, level = "Not ready", "bad"
    return {"overall": overall, "content": round(content_score),
            "account": round(account_score), "verdict": verdict, "level": level}


def optimize_email(subject, body):
    """Auto-correct an email to maximise inbox placement. Returns
    (new_subject, new_body) — re-scoring the result should approach 100%."""
    subject = subject or ""
    body = body or ""

    # 1) Subject: kill ALL-CAPS and shouting punctuation.
    letters = [c for c in subject if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        subject = subject.title()
    subject = _re.sub(r"[!]{2,}", "!", subject)
    subject = _re.sub(r"[?]{2,}", "?", subject)
    subject = _re.sub(r"\${2,}|%{2,}", "", subject).strip()
    if subject.count("!") > 1:
        subject = subject.replace("!", "", subject.count("!") - 1)

    # 2) Soften spam-trigger words in both subject and body (case-insensitive).
    def soften(s):
        for bad, good in SPAM_FIX.items():
            s = _re.sub(_re.escape(bad), good, s, flags=_re.IGNORECASE)
        return s
    subject, body = soften(subject), soften(body)

    # 3) Ensure personalisation.
    if "{{name}}" not in body:
        if "<" in body:
            body = "<p>Hi {{name}},</p>\n" + body
        else:
            body = "Hi {{name}},\n\n" + body

    # 4) Ensure a compliant footer with unsubscribe + view-in-browser.
    low = body.lower()
    if "{{unsubscribe_url}}" not in body and "/t/u/" not in body \
            and "unsubscribe" not in low:
        body += (
            '\n<hr><p style="font-size:11px;color:#888;text-align:center">'
            'You received this email because you opted in.<br>'
            '<a href="{{view_in_browser_url}}">View in browser</a> &middot; '
            '<a href="{{unsubscribe_url}}">Unsubscribe</a></p>')
    elif "{{view_in_browser_url}}" not in body and "view in browser" not in low:
        body += ('\n<p style="font-size:11px;color:#888;text-align:center">'
                 '<a href="{{view_in_browser_url}}">View in browser</a></p>')
    return subject.strip(), body
