"""Telegram text length helpers.

Telegram measures `text` and `caption` limits in **UTF-16 code units**, not
Python characters. An emoji like 🎉 is 1 Python char but 2 UTF-16 units; many
CJK glyphs are 1 unit. Counting with `len()` overestimates for emoji-heavy
content and silently truncates server-side.

Adapted from NousResearch/hermes-agent (MIT) — see ./NOTICE.
"""
from __future__ import annotations


def utf16_len(s: str) -> int:
    """Return the length of `s` in UTF-16 code units (Telegram's unit)."""
    return len(s.encode("utf-16-le")) // 2


def truncate_utf16(s: str, max_units: int) -> tuple[str, str]:
    """Split `s` into (head, tail) where utf16_len(head) <= max_units.

    Greedy by Python characters — gives up at most a few units short of the
    limit when a surrogate pair would straddle the boundary. Returns
    `(s, "")` when the whole string fits.
    """
    if utf16_len(s) <= max_units:
        return s, ""

    # Binary search the largest prefix that fits — O(log n) calls to utf16_len.
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if utf16_len(s[:mid]) <= max_units:
            lo = mid
        else:
            hi = mid - 1
    return s[:lo], s[lo:]
