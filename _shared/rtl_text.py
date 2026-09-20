"""Shared RTL-aware text helper for course-asset generation scripts (cover
banners, unit icons with captions, etc.).

Any script that draws text for a course must go through here instead of
calling `ImageDraw.text` directly, and must decide layout (alignment, which
side a logo/icon sits on) from `is_rtl(meta_json_language)` — never
hardcode left-to-right layout and only special-case Farsi as an afterthought.
A course's `meta.json` "language" field (e.g. "fa") is the single source of
truth for this; pass it in, don't re-detect from the text itself.

Requires `arabic_reshaper` and `python-bidi` (both already used for the
scam-tashkhis-farsi cover — confirmed available in this environment).
"""
import arabic_reshaper
from bidi.algorithm import get_display

# ISO language codes this project treats as right-to-left. Extend this set
# if a future course ships in another RTL language (e.g. Arabic "ar",
# Hebrew "he") rather than adding a one-off check elsewhere.
RTL_LANGUAGES = {"fa", "ar", "he", "ur"}


def is_rtl(language: str | None) -> bool:
    """language: a course's meta.json "language" field (e.g. "fa"), or None
    for the app's default (English, LTR)."""
    return (language or "").lower() in RTL_LANGUAGES


def shaped(text: str, language: str | None) -> str:
    """Returns text ready to hand to ImageDraw.text: reshaped + bidi-reordered
    for RTL languages (so Farsi/Arabic glyphs join and read right-to-left),
    or the plain string unchanged for LTR languages."""
    if not is_rtl(language):
        return text
    return get_display(arabic_reshaper.reshape(text))


def text_anchor_x(language: str | None, canvas_width: int, text_width: int, margin: int) -> int:
    """x-coordinate to draw text at, given the language's reading direction:
    right-aligned (text block's right edge at canvas_width - margin) for
    RTL, left-aligned (at margin) for LTR. Callers should use this instead
    of a hardcoded left-margin x position."""
    if is_rtl(language):
        return canvas_width - margin - text_width
    return margin


def logo_side(language: str | None) -> str:
    """Which physical side a logo/icon belongs on for this language's
    reading direction — 'right' for RTL (so the eye meets the logo first,
    same as it would meet a left-side logo in LTR), 'left' for LTR."""
    return "right" if is_rtl(language) else "left"
