"""Last.fm tag cleaning."""

import re
from typing import Iterable

MAX_TAGS_PER_LEVEL = 8

NOISE_TAGS = frozenset(
    {
        "seen live",
        "favorites",
        "favourites",
        "favorite",
        "albums i own",
        "awesome",
        "love",
        "good",
        "best",
        "my music",
        "spotify",
        "under 2000 listeners",
        "all",
        "male vocalists",
        "female vocalists",
    }
)

# Last.fm housekeeping tags. Nationalities and places are kept: where a band is from is useful context.
JUNK_TAGS = frozenset({"wrong track streaming", "reissue", "remaster", "remastered", "deluxe edition"})

# Too generic to characterize an album; kept, but ranked below any specific tag.
VAGUE_TAGS = frozenset({"alternative", "rock", "indie", "pop", "metal", "punk", "electronic", "experimental"})

YEAR_RE = re.compile(r"^\d{4}$")
_DECADE_RE = re.compile(r"^\d{2,4}s$")
# List-membership and chatter tags: "1001 albums you must hear...", "best of 2013", "top metal albums of
# the decade", "allboutguitarcom", and jokes like "a good girlfriend will have sex with me to this music".
_JUNK_RE = re.compile(
    r"^(wrong|incorrect|best of|top )\b|\balbums? (you|i|of|that)\b|\bgirlfriend\b|\b\d{4}\b.*\b\d{4}\b|\w+com$"
)


def tag_key(name: str) -> str:
    """Spelling-insensitive identity: `synth-pop`, `synth pop` and `synthpop` match."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def tag_order(name: str, count: int) -> tuple:
    return (name in VAGUE_TAGS, -count, name)


def clean_tags(tags: Iterable | None, max_n: int = MAX_TAGS_PER_LEVEL, exclude: Iterable[str | None] = ()) -> list[dict]:
    """Normalize `[{"name", "count"}]` (bare strings tolerated, count 0): lowercase,
    drop years/decades, noise, junk and echoes of `exclude` names (artist/album),
    merge spelling variants (best count wins), sort specific tags first then by
    count desc then name, truncate."""
    excluded = {tag_key(n) for n in exclude if n}
    best: dict[str, tuple[str, int]] = {}
    for tag in tags or []:
        if isinstance(tag, str):
            name, count = tag, 0
        else:
            name, count = tag.get("name"), tag.get("count") or 0
        if not name:
            continue
        name = name.strip().lower()
        if (
            not name
            or name in NOISE_TAGS
            or name in JUNK_TAGS
            or _JUNK_RE.search(name)
            or YEAR_RE.match(name)
            or _DECADE_RE.match(name)
            or tag_key(name) in excluded
        ):
            continue
        key = tag_key(name)
        if key not in best or (count, name) > (best[key][1], best[key][0]):
            best[key] = (name, count)
    ordered = sorted(best.values(), key=lambda item: tag_order(*item))
    return [{"name": name, "count": count} for name, count in ordered[:max_n]]
