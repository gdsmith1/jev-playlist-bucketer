"""Data-quality summaries over the per-album records: how well Last.fm covered the playlist."""

ARTIST_ONLY_LIMIT = 200  # rows kept in the artist-only list; the counts always cover every album


def _share(rows: list[dict]) -> dict:
    return {"albums": len(rows), "songs": sum(r["songs"] for r in rows)}


def quality_stats(records: list[dict]) -> dict:
    album_level = [r for r in records if r["has_album_tags"]]
    artist_only = [r for r in records if not r["has_album_tags"] and r["has_artist_tags"]]
    untagged = [r for r in records if not r["has_album_tags"] and not r["has_artist_tags"]]
    no_cover = [r for r in records if not r["cover"]]
    weakest = sorted(artist_only, key=lambda r: (-r["songs"], r["artist"], r["album"]))[:ARTIST_ONLY_LIMIT]
    return {"total": _share(records), "album_level": _share(album_level), "artist_only": _share(artist_only), "untagged": _share(untagged),
            "no_cover": _share(no_cover),
            "artist_only_list": [{"artist": r["artist"], "album": r["album"], "songs": r["songs"], "cover": r["cover"],
                                  "tags": [t["name"] for t in r["tags"][:6]]} for r in weakest]}
