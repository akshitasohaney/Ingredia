import unicodedata
import re
from typing import List


def normalize_text(text: str | None) -> str:
    """Deterministically normalize raw ingredient text.

    - Handles ``None`` safely.
    - Unicode NFKC normalisation.
    - Lower‑cases, collapses whitespace.
    - Replaces various dash/hyphen characters with a space.
    - Strips surrounding punctuation but **preserves parentheses**.
    - Keeps commas and slashes for later tokenisation.
    """
    if not text:
        return ""
    # Normalise unicode composition
    text = unicodedata.normalize("NFKC", text)
    # Lower‑case for case‑insensitive matching
    text = text.lower()
    # Replace dash‑like characters with a space (‑ – — etc.)
    text = re.sub(r"[\u2010-\u2015\-–—]", " ", text)
    # Collapse multiple whitespace characters
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_ingredients(normalized: str) -> List[str]:
    """Conservatively split a *normalized* ingredient string into individual tokens.

    Splits on commas (",") or slashes ("/") **only when they are not inside
    parentheses**. Whitespace is trimmed from each token.
    """
    if not normalized:
        return []
    parts: List[str] = []
    buf = ""
    depth = 0  # parenthesis nesting level
    for ch in normalized:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        if ch in ",/" and depth == 0:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def process_raw(text: str | None) -> List[str]:
    """Convenient helper that normalises *text* and returns a list of ingredient tokens.
    """
    normalized = normalize_text(text)
    return split_ingredients(normalized)
