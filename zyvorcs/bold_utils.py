"""
bold_utils.py  —  ZyvoRCS Unicode Bold Helpers
================================================
Bold works because the Unicode Math Bold glyphs are sent as literal text
via set_text() — no formatting API needed. RCS renders them visually bold
since they are different glyphs in the Unicode math block.

Usage in app.py / adb_engine.py:
    from bold_utils import _to_unicode_bold, _process_bold_markers
    from bold_utils import _apply_bold_selection, _apply_unbold_selection

    # Process {bold}...{/bold} tags before sending:
    processed = _process_bold_markers(raw_message)

Qt / MainWindow integration (if using PyQt):
    from bold_utils import _apply_bold_selection, _apply_unbold_selection
    MainWindow._apply_bold_selection   = _apply_bold_selection
    MainWindow._apply_unbold_selection = _apply_unbold_selection
"""

import re

# ── Build bold ↔ plain maps ────────────────────────────────────────────────────
_BOLD_MAP:   dict[str, str] = {}
_UNBOLD_MAP: dict[str, str] = {}

for i in range(26):
    _BOLD_MAP[chr(0x41 + i)] = chr(0x1D5D4 + i)   # A-Z  → 𝗔-𝗭
    _BOLD_MAP[chr(0x61 + i)] = chr(0x1D5EE + i)   # a-z  → 𝗮-𝘇
    _UNBOLD_MAP[chr(0x1D5D4 + i)] = chr(0x41 + i)  # 𝗔-𝗭 → A-Z
    _UNBOLD_MAP[chr(0x1D5EE + i)] = chr(0x61 + i)  # 𝗮-𝘇 → a-z

for i in range(10):
    _BOLD_MAP[chr(0x30 + i)] = chr(0x1D7EC + i)   # 0-9  → 𝟬-𝟵
    _UNBOLD_MAP[chr(0x1D7EC + i)] = chr(0x30 + i)  # 𝟬-𝟵 → 0-9


# ── Core converters ───────────────────────────────────────────────────────────

def _to_unicode_bold(text: str) -> str:
    """Convert ASCII letters/digits in *text* to Unicode Math Bold Sans glyphs."""
    return ''.join(_BOLD_MAP.get(c, c) for c in text)


def _from_unicode_bold(text: str) -> str:
    """Revert Unicode Math Bold Sans glyphs back to plain ASCII."""
    return ''.join(_UNBOLD_MAP.get(c, c) for c in text)


# ── Template tag processor ────────────────────────────────────────────────────

def _process_bold_markers(message: str) -> str:
    """
    Replace every ``{bold}...{/bold}`` tag in *message* with the Unicode
    bold equivalent of the enclosed text.

    Example:
        >>> _process_bold_markers("Hi {bold}Alice{/bold}, your renewal is due.")
        'Hi 𝗔𝗹𝗶𝗰𝗲, your renewal is due.'
    """
    return re.sub(
        r'\{bold\}(.*?)\{/bold\}',
        lambda m: _to_unicode_bold(m.group(1)),
        message,
        flags=re.DOTALL,
    )


# ── Optional PyQt helpers (bound to MainWindow if needed) ────────────────────

def _apply_bold_selection(self) -> None:  # type: ignore[override]
    """
    PyQt slot — converts the selected text in ``self.msg_edit`` to
    Unicode bold in-place.  Bind with::

        MainWindow._apply_bold_selection = _apply_bold_selection
    """
    cursor = self.msg_edit.textCursor()
    if not cursor.hasSelection():
        return
    sel = cursor.selectedText()
    cursor.insertText(_to_unicode_bold(sel))


def _apply_unbold_selection(self) -> None:  # type: ignore[override]
    """
    PyQt slot — reverts the selected Unicode bold text in ``self.msg_edit``
    back to plain ASCII.  Bind with::

        MainWindow._apply_unbold_selection = _apply_unbold_selection
    """
    cursor = self.msg_edit.textCursor()
    if not cursor.hasSelection():
        return
    sel = cursor.selectedText()
    cursor.insertText(_from_unicode_bold(sel))
