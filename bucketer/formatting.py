"""Builds the album text jev receives (also its cache key) and the run summary."""

from collections.abc import Iterable

from .models import Enrichment
from .names import clean_album, is_unknown_album, primary_artist
from .tags import YEAR_RE, tag_order

MAX_ITEMS_PER_LEVEL = 6
MAX_TEXT_LEN = 600


def _level_items(tags: list[dict] | None) -> list[str]:
    ordered = sorted(
        tags or [],
        key=lambda t: tag_order(t["name"].strip().lower(), t.get("count") or 0),
    )
    items: list[str] = []
    for tag in ordered:
        name = tag["name"].strip().lower()
        if name and name not in items:
            items.append(name)
    return items[:MAX_ITEMS_PER_LEVEL]


def format_for_jev(artist: str, album: str, release_date: str, enrichment: Enrichment) -> str:
    """Deterministic album-level text sent to jev (and used as its cache key).
    Semantic evidence only: no counts, track titles, durations or ids."""
    artist = primary_artist(artist)
    year = (release_date or "").strip()[:4]
    if is_unknown_album(album):
        head = f"Artist: {artist}"
    else:
        head = f"Album: {clean_album(album)} by {artist}" + (f" ({year})" if YEAR_RE.match(year) else "")

    seen: set[str] = set()
    lines = [head]
    for name, tags in (("album", enrichment.album_tags), ("artist", enrichment.artist_tags)):
        shown = [item for item in _level_items(tags) if item not in seen]
        seen.update(shown)
        if shown:
            lines.append(f"{name.capitalize()} tags (strongest first): {', '.join(shown)}")

    similar = list(enrichment.similar_artists)
    while True:
        out = lines + ([f"Similar artists: {', '.join(str(a) for a in similar)}"] if similar else [])
        text = "\n".join(out)
        if len(text) <= MAX_TEXT_LEN or not similar:
            return text
        similar = similar[:-1]


def coverage_stats(enrichments: Iterable[Enrichment]) -> dict[str, int]:
    stats = {"albums": 0, "album": 0, "artist": 0, "any": 0, "none": 0}
    for enrichment in enrichments:
        stats["albums"] += 1
        album, artist = bool(enrichment.album_tags), bool(enrichment.artist_tags)
        stats["album"] += album
        stats["artist"] += artist
        if album or artist:
            stats["any"] += 1
        else:
            stats["none"] += 1
    return stats


def format_run_stats(coverage: dict, provider_stats: dict, elapsed: float) -> str:
    n = coverage["albums"]
    return (
        f"lastfm coverage over {n} albums: album {coverage['album']}/{n}  "
        f"artist {coverage['artist']}/{n}  any {coverage['any']}/{n}  none {coverage['none']}/{n}\n"
        f"lastfm calls: {provider_stats.get('calls', 0)}  "
        f"cache_hits: {provider_stats.get('cache_hits', 0)}  "
        f"errors: {provider_stats.get('errors', 0)}   elapsed: {elapsed:.0f}s"
    )
