"""
AI Center engine.

These helpers power the AI Center: subject-line generation, full email
drafting, spam scoring, reply drafting and send-time prediction.

Design note
-----------
The functions below use deterministic, rule-based generation so the feature
works **offline and for free** in any environment. Each one is written behind a
single seam (`_llm_complete`) so you can drop in a real LLM — e.g. the Anthropic
Claude API — by implementing that one function. When a real model is wired up,
set ``USE_LLM = True``; otherwise the built-in generator is used.
"""
import re
import random

USE_LLM = False  # flip to True once _llm_complete() is wired to a real model.


def _llm_complete(prompt, max_tokens=400):  # pragma: no cover - integration seam
    """Placeholder for a real LLM call.

    To use Claude, install `anthropic`, set ANTHROPIC_API_KEY, and implement:

        from anthropic import Anthropic
        msg = Anthropic().messages.create(
            model="claude-opus-4-8",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- #
#  Subject lines
# --------------------------------------------------------------------------- #

_SUBJECT_PATTERNS = [
    "{emoji} {topic} — here's what's new",
    "Don't miss out on {topic}",
    "{topic}: {benefit} inside",
    "Your {topic} update is ready",
    "{n} ways to {verb} with {topic}",
    "Quick question about {topic}",
    "Last chance: {topic}",
    "[New] {topic} just got better",
    "{name}, your {topic} is waiting",
    "How to {verb} your {topic} today",
]
_EMOJI = ["🚀", "✨", "🎉", "🔥", "📣", "💡", "⏰", "🎁"]
_BENEFITS = ["save time", "boost results", "get ahead", "do more", "win big"]
_VERBS = ["improve", "grow", "supercharge", "simplify", "master", "transform"]


def generate_subjects(topic, tone="friendly", n=6):
    topic = (topic or "your campaign").strip()
    out = []
    for pat in random.sample(_SUBJECT_PATTERNS, min(n, len(_SUBJECT_PATTERNS))):
        s = pat.format(
            topic=topic.capitalize(), emoji=random.choice(_EMOJI),
            benefit=random.choice(_BENEFITS), verb=random.choice(_VERBS),
            n=random.choice([3, 5, 7]), name="{{name}}")
        if tone == "urgent":
            s = s.replace("Don't miss out", "Ends tonight")
        out.append(s)
    return out


# --------------------------------------------------------------------------- #
#  Email writer
# --------------------------------------------------------------------------- #

_TONE_OPENERS = {
    "friendly": "Hi {{name}},\n\nHope you're having a great week!",
    "professional": "Hello {{name}},\n\nThank you for your continued interest.",
    "urgent": "Hi {{name}},\n\nThis is time-sensitive, so I'll keep it short.",
    "casual": "Hey {{name}}! 👋",
}


def write_email(topic, tone="friendly", cta="Learn more", audience="customers"):
    topic = (topic or "our latest update").strip()
    opener = _TONE_OPENERS.get(tone, _TONE_OPENERS["friendly"])
    body = (
        f"{opener}\n\n"
        f"We wanted to tell you about {topic}. We built it specifically for "
        f"{audience} like you who want to get more done with less effort.\n\n"
        f"Here's what you can expect:\n"
        f"  • Faster results from day one\n"
        f"  • A simple, intuitive experience\n"
        f"  • Support whenever you need it\n\n"
        f"Ready to see it in action?\n\n"
        f"👉 {cta}\n\n"
        f"Cheers,\nThe Team"
    )
    return body


# --------------------------------------------------------------------------- #
#  Full AI email generator — assembles a branded, personalised HTML email
#  (subject, preview text, heading, body, CTA button, footer) from a handful
#  of inputs. Deterministic and offline; swap `_llm_complete` for a real model
#  to upgrade the copy without changing any callers.
# --------------------------------------------------------------------------- #

# Accent colour + a friendly opening line per industry.
INDUSTRY_PRESETS = {
    "Banking": ("#1e3a8a", "manage your money with confidence"),
    "Insurance": ("#0f766e", "protect what matters most"),
    "Healthcare": ("#0e7490", "care that's always within reach"),
    "Education": ("#7c3aed", "keep learning and growing"),
    "E-commerce": ("#db2777", "handpicked just for you"),
    "Restaurant": ("#b91c1c", "something delicious is waiting"),
    "Travel": ("#0891b2", "your next journey starts here"),
    "Real Estate": ("#92400e", "find a place to call home"),
    "SaaS": ("#4f46e5", "do more with less effort"),
    "Corporate": ("#334155", "a quick update from our team"),
    "Automobile": ("#1f2937", "the road ahead looks great"),
    "Telecom": ("#2563eb", "stay connected, always"),
    "Fitness": ("#16a34a", "your goals, within reach"),
    "Hotel": ("#a16207", "your comfort is our priority"),
    "Beauty & Salon": ("#be185d", "look and feel your best"),
    "Legal": ("#374151", "clear guidance you can trust"),
    "Manufacturing": ("#c2410c", "built to last"),
    "Logistics": ("#0369a1", "delivered on time, every time"),
    "Entertainment": ("#7e22ce", "the fun is about to begin"),
    "Non-Profit": ("#15803d", "together we make a difference"),
}

INDUSTRIES = list(INDUSTRY_PRESETS.keys())
EMAIL_TYPES = ["Newsletter", "Promotion", "Announcement", "Welcome",
               "Re-engagement", "Event Invite", "Product Update",
               "Transactional Receipt"]
GOALS = ["Drive sales", "Announce a product", "Share news", "Get sign-ups",
         "Book appointments", "Re-engage inactive contacts", "Collect feedback"]


def generate_email(industry="", email_type="Newsletter", goal="", audience="customers",
                   tone="friendly", length="medium", cta_style="button",
                   language="english", spam_safe=True, company="{{company}}"):
    """Return a complete email dict: subject, preview_text and HTML content
    (heading + body + CTA + footer), branded to the industry and personalised
    with merge tags."""
    accent, opener_line = INDUSTRY_PRESETS.get(industry, ("#4f46e5", "we've got something for you"))
    topic = (goal or email_type or industry or "an update").strip()

    subject = generate_subjects(topic, tone, 1)[0]
    preview_text = f"{opener_line.capitalize()} — {audience.rstrip('s').capitalize()}-first, no fluff."
    heading = _headline(topic, tone)
    cta = generate_ctas(goal or "get started")[0]

    # Body paragraphs scale with the requested length.
    para = {
        "short": 1, "medium": 2, "long": 3,
    }.get((length or "medium").lower(), 2)
    intro = (f"Hi {{{{name}}}}," if tone != "casual" else "Hey {{name}}! 👋")
    lines = [
        f"{opener_line.capitalize()} — here's {topic.lower()} for {audience}.",
        "We kept it short and useful, with everything you need in one place.",
        "Have a question? Just reply to this email and a real person will help.",
    ][:para]
    body_paras = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{l}</p>'
                         for l in lines)

    if cta_style == "link":
        cta_html = (f'<p style="margin:18px 0"><a href="#" '
                    f'style="color:{accent};font-weight:600">{cta} →</a></p>')
    else:
        cta_html = (f'<p style="margin:24px 0"><a href="#" '
                    f'style="background:{accent};color:#fff;text-decoration:none;'
                    f'padding:12px 22px;border-radius:8px;font-weight:600;'
                    f'display:inline-block">{cta}</a></p>')

    content = (
        f'<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,'
        f'sans-serif;color:#1f2937">'
        f'<div style="background:{accent};height:6px;border-radius:6px 6px 0 0"></div>'
        f'<div style="padding:28px 26px">'
        f'<h1 style="margin:0 0 16px;font-size:22px;color:{accent}">{heading}</h1>'
        f'<p style="margin:0 0 14px;line-height:1.6">{intro}</p>'
        f'{body_paras}{cta_html}'
        f'<p style="margin:18px 0 0;line-height:1.6">Warm regards,<br>'
        f'The {company} Team</p>'
        f'</div>'
        f'<hr style="border:none;border-top:1px solid #e5e7eb">'
        f'<p style="font-size:11px;color:#9ca3af;text-align:center;padding:0 20px 20px">'
        f'You received this email because you opted in.<br>'
        f'<a href="{{{{view_in_browser_url}}}}">View in browser</a> &middot; '
        f'<a href="{{{{unsubscribe_url}}}}">Unsubscribe</a></p>'
        f'</div>'
    )

    if (language or "english").lower() != "english":
        tr = translate(content, language)
        content = tr.get("text", content)
        subject = translate(subject, language).get("text", subject)

    result = {"subject": subject, "preview_text": preview_text,
              "heading": heading, "cta": cta, "content": content,
              "accent": accent}
    return result


def _headline(topic, tone):
    topic = topic.strip().rstrip(".")
    if tone == "urgent":
        return f"{topic.capitalize()} — don't miss out"
    if tone == "professional":
        return topic.capitalize()
    return f"{topic.capitalize()} 🎉"


def generate_reply(incoming, tone="professional"):
    incoming = (incoming or "").strip()
    sentiment = "positive"
    low = incoming.lower()
    if any(w in low for w in ["refund", "angry", "cancel", "unhappy", "complaint", "broken"]):
        sentiment = "negative"
    elif any(w in low for w in ["thank", "great", "love", "awesome", "happy"]):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    if sentiment == "negative":
        return ("Hi {{name}},\n\nI'm really sorry for the trouble — that's not the "
                "experience we want for you. I've escalated this and we'll make it "
                "right. Could you share a few more details so I can resolve it "
                "quickly?\n\nThank you for your patience,\nSupport")
    if sentiment == "positive":
        return ("Hi {{name}},\n\nThank you so much for the kind words — it genuinely "
                "made our day! 🙌 If there's anything else we can help with, just "
                "reply here.\n\nBest,\nThe Team")
    return ("Hi {{name}},\n\nThanks for reaching out! Happy to help with this. "
            "Here's the information you need… let me know if anything is unclear.\n\n"
            "Best regards,\nThe Team")


# --------------------------------------------------------------------------- #
#  Spam scoring  (real, explainable heuristics)
# --------------------------------------------------------------------------- #

_SPAM_WORDS = [
    "free", "guarantee", "winner", "cash", "credit", "click here", "buy now",
    "limited time", "act now", "urgent", "100%", "risk-free", "no obligation",
    "viagra", "casino", "lottery", "income", "cheap", "earn money", "double your",
]


def spam_score(subject, body):
    """Return a 0–100 *deliverability* score (higher = better) plus issues."""
    subject = subject or ""
    body = body or ""
    text = f"{subject}\n{body}"
    low = text.lower()
    issues = []
    penalty = 0

    found = sorted({w for w in _SPAM_WORDS if w in low})
    if found:
        penalty += min(30, 6 * len(found))
        issues.append(f"Spam-trigger words: {', '.join(found[:6])}")

    # ALL CAPS in subject
    letters = [c for c in subject if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        penalty += 12
        issues.append("Subject is mostly UPPERCASE")

    # Excessive punctuation
    if subject.count("!") >= 2 or "!!!" in text:
        penalty += 10
        issues.append("Excessive exclamation marks")

    # Too many links
    links = len(re.findall(r"https?://", low))
    if links > 5:
        penalty += 10
        issues.append(f"{links} links (keep it under 5)")

    # Spammy symbols
    if re.search(r"\$\d|\d+%\s*off|💰|🤑", low):
        penalty += 6
        issues.append("Money/discount symbols can trip filters")

    # Missing unsubscribe
    if "unsubscribe" not in low:
        penalty += 12
        issues.append("No unsubscribe link found (required by law & filters)")

    # Image-only / very short body
    if len(re.sub(r"\s+", "", body)) < 40:
        penalty += 8
        issues.append("Body is very short / thin on text")

    # Subject length
    if len(subject) > 70:
        penalty += 5
        issues.append("Subject is long — aim for under 60 characters")

    score = max(0, 100 - penalty)
    verdict = "Inbox" if score >= 80 else ("Promotions/Risky" if score >= 55 else "Spam likely")
    if not issues:
        issues.append("No major spam signals detected 🎉")
    return {"score": score, "verdict": verdict, "issues": issues,
            "trigger_words": found}


# --------------------------------------------------------------------------- #
#  Send-time prediction (heuristic best-practice model)
# --------------------------------------------------------------------------- #


def generate_ctas(context="sign up"):
    context = (context or "get started").strip().rstrip(".")
    base = [
        f"Get started — {context} now",
        f"Yes, I want to {context}",
        f"Claim your spot",
        f"Start your free trial",
        f"Show me how →",
        f"Unlock {context} today",
        f"Count me in",
        f"See it in action",
    ]
    random.shuffle(base)
    return base[:6]


def ab_subjects(topic):
    """Return two distinct subject-line variants for A/B testing."""
    pool = generate_subjects(topic, n=6)
    a = pool[0]
    b = next((s for s in pool[1:] if s != a), pool[-1])
    return {"A": a, "B": b,
            "tip": "Send variant A to ~10% and B to ~10%; the winner goes to the rest."}


_REWRITE = {
    "shorter": lambda t: " ".join(t.split()[:max(8, len(t.split()) // 2)]) +
    ("…" if len(t.split()) > 8 else ""),
    "formal": lambda t: t.replace("Hi", "Dear").replace("Hey", "Dear")
    .replace("!", ".").replace("👋", "").replace("🚀", ""),
    "friendly": lambda t: ("Hey there! " + t).replace("Dear", "Hi"),
    "urgent": lambda t: "⏰ " + t.rstrip(".") + " — but hurry, this won't last!",
    "persuasive": lambda t: t.rstrip(".") + ". Thousands already made the switch — "
    "don't get left behind.",
}


def rewrite(text, goal="shorter"):
    fn = _REWRITE.get(goal, _REWRITE["shorter"])
    return fn((text or "").strip())


# Minimal localisation glossary for greeting / sign-off (honest "demo" translate;
# wire _llm_complete for full-body translation).
_GLOSSARY = {
    "spanish": {"Hi": "Hola", "Hello": "Hola", "Thanks": "Gracias",
                "The Team": "El Equipo", "Learn more": "Más información"},
    "french": {"Hi": "Bonjour", "Hello": "Bonjour", "Thanks": "Merci",
               "The Team": "L'équipe", "Learn more": "En savoir plus"},
    "german": {"Hi": "Hallo", "Hello": "Hallo", "Thanks": "Danke",
               "The Team": "Das Team", "Learn more": "Mehr erfahren"},
    "hindi": {"Hi": "नमस्ते", "Hello": "नमस्ते", "Thanks": "धन्यवाद",
              "The Team": "टीम", "Learn more": "और जानें"},
}


def translate(text, language="spanish"):
    text = text or ""
    glossary = _GLOSSARY.get(language.lower())
    if not glossary:
        return {"text": text, "note": "Unsupported language in the built-in glossary."}
    out = text
    for en, tr in glossary.items():
        out = out.replace(en, tr)
    return {"text": out,
            "note": f"Greetings/sign-offs localised to {language.title()}. "
                    "Enable the LLM for full-quality body translation."}


def personalize(template, name="Alex", company="Acme", city="Austin"):
    """Resolve merge tags + suggest dynamic blocks."""
    template = template or "Hi {{name}}, we noticed {{company}} is based in {{city}}."
    resolved = (template.replace("{{name}}", name).replace("{{company}}", company)
                .replace("{{city}}", city))
    tags = [t for t in ("{{name}}", "{{company}}", "{{city}}", "{{first_name}}")
            if t in template]
    return {"resolved": resolved, "tags_used": tags or ["{{name}}"],
            "preview_for": f"{name} @ {company}"}


def analyze_tone(text):
    """Classify the dominant tone of a piece of copy (heuristic)."""
    low = (text or "").lower()
    signals = {
        "Urgent": ["now", "hurry", "today", "last chance", "ends", "!", "immediately"],
        "Friendly": ["hi", "hey", "thanks", "😊", "👋", "hope", "great"],
        "Formal": ["dear", "regards", "sincerely", "kindly", "please find"],
        "Persuasive": ["you", "free", "save", "exclusive", "guarantee", "proven"],
        "Salesy": ["buy", "discount", "offer", "deal", "% off", "limited"],
    }
    scores = {t: sum(low.count(w) for w in ws) for t, ws in signals.items()}
    dominant = max(scores, key=scores.get) if any(scores.values()) else "Neutral"
    exclaim = (text or "").count("!")
    readability = "Easy" if len((text or "").split()) < 120 else "Dense"
    return {"tone": dominant, "scores": scores, "exclaims": exclaim,
            "readability": readability,
            "tip": "Lots of exclamation marks can hurt deliverability." if exclaim > 2
            else "Tone looks balanced for most audiences."}


def detect_reply_intent(text):
    """Detect the intent of an inbound reply so it can be auto-routed."""
    low = (text or "").lower()
    rules = [
        ("Unsubscribe", ["unsubscribe", "remove me", "stop emailing", "opt out", "opt-out"]),
        ("Out of office", ["out of office", "on leave", "vacation", "away until", "ooo"]),
        ("Interested", ["interested", "tell me more", "sounds good", "let's talk",
                        "book a", "demo", "pricing"]),
        ("Not interested", ["not interested", "no thanks", "remove", "not a fit"]),
        ("Complaint", ["spam", "stop", "angry", "report", "illegal"]),
        ("Question", ["?", "how do", "can you", "what is", "when"]),
    ]
    for label, kws in rules:
        if any(k in low for k in kws):
            return {"intent": label,
                    "action": {
                        "Unsubscribe": "Auto-suppress this contact",
                        "Out of office": "Snooze follow-up 7 days",
                        "Interested": "Route to sales + create task",
                        "Not interested": "Mark closed-lost",
                        "Complaint": "Suppress + flag for review",
                        "Question": "Route to support",
                    }[label]}
    return {"intent": "Neutral", "action": "Log and continue sequence"}


def predict_bounce(email):
    """Predict the likelihood an address will bounce, from verification signals."""
    from .verify import verify_email
    v = verify_email(email)
    risk = 100 - v["score"]
    if v["result"] == "invalid":
        risk = max(risk, 85)
    band = "High" if risk >= 60 else "Medium" if risk >= 30 else "Low"
    reasons = []
    ch = v.get("checks", {})
    if not ch.get("mx", True):
        reasons.append("No MX records")
    if not ch.get("smtp", True):
        reasons.append("Mailbox not confirmed")
    if not ch.get("not_role", True):
        reasons.append("Role address")
    if not ch.get("disposable", True):
        reasons.append("Disposable domain")
    if v.get("suggestion"):
        reasons.append(f"Likely typo — {v['local']}@{v['suggestion']}?")
    return {"email": v["email"], "bounce_risk": risk, "band": band,
            "recommend": "Remove before sending" if band == "High"
            else "Verify first" if band == "Medium" else "Safe to send",
            "reasons": reasons or ["No strong bounce signals"]}


def optimize_subject(subject):
    """Score a subject line and suggest concrete improvements."""
    subject = (subject or "").strip()
    score = 100
    tips = []
    n = len(subject)
    if n == 0:
        return {"score": 0, "grade": "—", "tips": ["Enter a subject line."],
                "length": 0, "emoji": False}
    if n > 60:
        score -= 15
        tips.append(f"Shorten to under 60 chars (currently {n}) — mobile truncates.")
    elif n < 20:
        score -= 8
        tips.append("A little longer (30–50 chars) often reads better.")
    if subject.count("!") >= 1:
        score -= 10
        tips.append("Drop exclamation marks — they trip spam filters.")
    if subject.isupper() or sum(c.isupper() for c in subject if c.isalpha()) > len(subject) * 0.5:
        score -= 12
        tips.append("Avoid ALL CAPS.")
    low = subject.lower()
    spammy = [w for w in _SPAM_WORDS if w in low]
    if spammy:
        score -= 8 * len(spammy)
        tips.append(f"Remove spammy words: {', '.join(spammy[:4])}.")
    has_emoji = any(ord(c) > 0x2600 for c in subject)
    if not has_emoji:
        tips.append("One relevant emoji can lift opens ~5%.")
    if "{{" not in subject:
        tips.append("Personalise with {{name}} for higher opens.")
    score = max(0, min(100, score))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"
    return {"score": score, "grade": grade, "tips": tips or ["Looks great!"],
            "length": n, "emoji": has_emoji}


def predict_send_time(audience="general", timezone="recipient"):
    table = {
        "general": ("Tuesday", "10:00", 24.1),
        "b2b": ("Tuesday", "09:00", 27.5),
        "b2c": ("Thursday", "20:00", 21.8),
        "ecommerce": ("Saturday", "11:00", 23.2),
        "newsletter": ("Wednesday", "08:00", 26.0),
    }
    day, time, rate = table.get(audience, table["general"])
    return {
        "best_day": day, "best_time": time, "expected_open_rate": rate,
        "timezone": timezone,
        "runner_up": "Thursday 14:00",
        "note": "Based on aggregate engagement patterns for this audience type. "
                "Optimised per-recipient when send-time AI is enabled.",
    }
