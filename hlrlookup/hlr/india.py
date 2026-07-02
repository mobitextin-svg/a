"""
Indian mobile number (MSISDN) helpers.

India numbering plan for mobiles:
  - Country calling code: +91
  - National mobile numbers are 10 digits.
  - The first digit is 6, 7, 8 or 9. (5xxxxxxxxx is being introduced but is
    not yet in general public use, so it is treated as invalid by default.)

Accepted input forms (all normalise to a 10-digit national number):
  9876543210, 09876543210, 919876543210, +91 98765 43210, 0091-9876543210

IMPORTANT — operator/circle guessing:
  Because of Mobile Number Portability (MNP), the numeric range of a number no
  longer reliably tells you the current operator. ``guess_operator`` returns a
  *best-effort* label based on the original allocation series and is only meant
  as a fallback when a live HLR lookup is unavailable. Trust the HLR result,
  not the guess, for the real current network.
"""

import re

# Telecom "circles" (service areas) keyed by the first two digits of the
# national number are NOT derivable post-MNP, so we do not fabricate them.

# Best-effort original-allocation operator hints, keyed by the leading digit.
# This is deliberately coarse and clearly heuristic (see module docstring).
_OPERATOR_HINTS = {
    "9": "Legacy / mixed (Airtel, Vi, BSNL, Jio)",
    "8": "Mixed (Jio, Airtel, Vi)",
    "7": "Mixed (Jio, Airtel, Vi)",
    "6": "Newer series (largely Jio)",
}

_DIGITS_RE = re.compile(r"\d")


def _digits_only(raw: str) -> str:
    return "".join(_DIGITS_RE.findall(raw or ""))


def normalize_msisdn(raw: str):
    """
    Turn a messy input string into a canonical 10-digit Indian national number.

    Returns the 10-digit string on success, or ``None`` if the input cannot be
    interpreted as an Indian mobile number.
    """
    digits = _digits_only(raw)
    if not digits:
        return None

    # Strip international / trunk prefixes.
    if digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10:
        return None
    if digits[0] not in "6789":
        return None
    return digits


def validate_indian_mobile(raw: str) -> bool:
    """True if ``raw`` is a syntactically valid Indian mobile number."""
    return normalize_msisdn(raw) is not None


def to_e164(national10: str) -> str:
    """Format a 10-digit national number as E.164 (+91XXXXXXXXXX)."""
    return "+91" + national10


def guess_operator(national10: str) -> str:
    """Best-effort, MNP-unaware operator hint. See module docstring."""
    if not national10:
        return "Unknown"
    return _OPERATOR_HINTS.get(national10[0], "Unknown")
