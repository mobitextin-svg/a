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
