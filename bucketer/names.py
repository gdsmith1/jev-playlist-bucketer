"""Artist and album name normalization."""

import re

UNKNOWN_ALBUMS = frozenset({"", "unknown", "unknown album", "[unknown]", "<unknown>"})

_ARTIST_SPLIT_RE = re.compile(r";\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+|\s+&\s+", re.IGNORECASE)

_TRAILING_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]\s*$")

_ALBUM_PAREN_RE = re.compile(
    r"\s*\([^()]*\b(?:deluxe|remaster(?:ed)?|reissue|expanded|edition|anniversary|bonus|version)\b[^()]*\)\s*$",
    re.IGNORECASE,
)
_ALBUM_DASH_RE = re.compile(
    r"\s+-\s+[^-]*\b(?:deluxe|remaster(?:ed)?|reissue|expanded|edition|anniversary|bonus|version)\b.*$",
    re.IGNORECASE,
)


def primary_artist(s: str | None) -> str:
    s = (s or "").strip()
    parts = _ARTIST_SPLIT_RE.split(s, maxsplit=1)
    return parts[0].strip() or s


def artist_candidates(s: str | None) -> list[str]:
    """Lookup attempts in order: primary artist, then the full string if different."""
    full = (s or "").strip()
    primary = primary_artist(full)
    return [primary] if primary == full else [primary, full]


def _strip_repeatedly(s: str | None, patterns: list[re.Pattern]) -> str:
    original = (s or "").strip()
    current = original
    while True:
        previous = current
        for pattern in patterns:
            current = pattern.sub("", current).strip()
        if current == previous:
            break
    return current or original


def clean_album(s: str | None) -> str:
    return _strip_repeatedly(s, [_TRAILING_BRACKET_RE, _ALBUM_PAREN_RE, _ALBUM_DASH_RE])


def is_unknown_album(album: str | None) -> bool:
    return (album or "").strip().lower() in UNKNOWN_ALBUMS
