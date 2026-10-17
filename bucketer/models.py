"""Plain data shapes passed between modules."""

from dataclasses import dataclass, field


@dataclass
class Enrichment:
    """Cleaned Last.fm data for one album. A `None` tag list means the lookup found nothing."""

    album_tags: list[dict] | None = None  # [{"name", "count"}]
    artist_tags: list[dict] | None = None
    similar_artists: list[str] = field(default_factory=list)


@dataclass
class Group:
    """Songs that share one jev decision: same primary artist and cleaned album."""

    key: str
    artist: str
    album: str
    release_date: str
    rows: list[int] = field(default_factory=list)  # indexes into the processed song lines
