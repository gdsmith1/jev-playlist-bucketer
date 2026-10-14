import json
import os

import requests

from enrichment import (
    JsonCache,
    Throttle,
    artist_candidates,
    clean_album,
    clean_tags,
    empty_enrichment,
    http_get_json,
)

MB_USER_AGENT = "jev-playlist-bucketer/0.1 ( gibson.smith@liatrio.com )"
MB_MIN_INTERVAL = 1.0  # seconds between MusicBrainz requests
MB_BASE = "https://musicbrainz.org/ws/2"
MIN_SCORE = 90
LEGACY_CACHE = "mb_cache.json"
# Album names that legitimately describe a Live/Compilation release group.
_SECONDARY_HINTS = {"Live": ("live",), "Compilation": ("greatest hits", "best of", "compilation", "collection", "anthology", "hits")}


def _lucene(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def _norm(s):
    return (s or "").strip().lower()


def _genres(items):
    """Genre names ordered by vote count desc (then name); non-positive counts dropped."""
    ranked = sorted(
        (g for g in items or [] if (g.get("count") or 0) > 0 and (g.get("name") or "").strip()),
        key=lambda g: (-g["count"], g["name"].strip().lower()),
    )
    out = []
    for g in ranked:
        name = g["name"].strip().lower()
        if name not in out:
            out.append(name)
    return out


def _level(genres, tags):
    if not genres and not tags:
        return None
    return {"genres": genres, "tags": tags}


def migrate_legacy(track_cache, legacy):
    """Fold old `mb_cache.json` entries ({isrc: {artist, track, tags: [str]|null}}) into the
    `track` section. Old entries only kept flat tag names, so names become `genres`
    (empty `tags`); null or empty lists become null. Existing entries are not overwritten.
    Returns the number migrated."""
    n = 0
    for isrc, entry in legacy.items():
        if isrc in track_cache or not isinstance(entry, dict):
            continue
        names = [t for t in (entry.get("tags") or []) if isinstance(t, str) and t.strip()]
        track_cache[isrc] = {"genres": [t.strip().lower() for t in names], "tags": []} if names else None
        n += 1
    return n


class Provider:
    """MusicBrainz: recording (ISRC) -> release-group (album) -> artist."""

    name = "musicbrainz"

    def __init__(self, cache_dir="."):
        self.cache = JsonCache(os.path.join(cache_dir, "musicbrainz_cache.json"))
        for section in ("artist", "album", "track"):
            self.cache.section(section)
        legacy_path = os.path.join(cache_dir, LEGACY_CACHE)
        if os.path.exists(legacy_path):
            with open(legacy_path) as f:
                migrate_legacy(self.cache.section("track"), json.load(f))
        self.throttle = Throttle(MB_MIN_INTERVAL)
        self.session = requests.Session()
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0}

    def _get(self, path, params):
        self.stats["calls"] += 1
        return http_get_json(
            self.session,
            f"{MB_BASE}/{path}",
            params={**params, "fmt": "json"},
            headers={"User-Agent": MB_USER_AGENT},
            throttle=self.throttle,
        )

    # Each _lookup returns (ok, entry). ok=False: transient failure, do not cache.
    # entry None = genuine not found (cached as null).

    def _lookup_track(self, isrc):
        status, data = self._get(f"isrc/{isrc}", {"inc": "tags+artist-credits"})
        if status == 404:
            return True, None
        if status != 200 or data is None:
            return False, None
        recordings = data.get("recordings") or []
        if not recordings:
            return True, None
        status, rec = self._get(f"recording/{recordings[0]['id']}", {"inc": "genres+tags+artist-credits"})
        if status != 200 or rec is None:
            return False, None
        credit = (rec.get("artist-credit") or [{}])[0]
        entry = {
            "genres": _genres(rec.get("genres")),
            "tags": clean_tags([t for t in rec.get("tags") or [] if (t.get("count") or 0) > 0]),
            "artist_mbid": (credit.get("artist") or {}).get("id"),
            "matched": (rec.get("title") or "").lower() or None,
        }
        return True, entry

    def _album_ok(self, album, hit):
        """Mismatch guard: skip Live/Compilation release groups unless our album name says so."""
        for sec in hit.get("secondary-types") or []:
            hints = _SECONDARY_HINTS.get(sec)
            if hints and not any(h in album.lower() for h in hints):
                return False
        return True

    def _search_release_group(self, artist, album):
        query = f'releasegroup:"{_lucene(album)}" AND artist:"{_lucene(artist)}"'
        status, data = self._get("release-group", {"query": query, "limit": 3})
        if status != 200 or data is None:
            return False, None
        for hit in data.get("release-groups") or []:
            if (hit.get("score") or 0) < MIN_SCORE:
                break  # sorted by score; nothing further qualifies
            if not self._album_ok(album, hit):
                continue
            tags = clean_tags([t for t in hit.get("tags") or [] if (t.get("count") or 0) > 0])
            secondary = [s.lower() for s in hit.get("secondary-types") or []]
            extras = {}
            if hit.get("primary-type"):
                extras["album_type"] = hit["primary-type"]
            if secondary:
                extras["album_secondary"] = [s.capitalize() for s in secondary]
            if hit.get("first-release-date"):
                extras["first_release_date"] = hit["first-release-date"]
            return True, {
                "genres": [],
                "tags": tags,
                "extras": extras,
                "matched": (hit.get("title") or "").lower() or None,
            }
        return True, None

    def _lookup_album(self, artist, album):
        cleaned = clean_album(album)
        ok, entry = self._search_release_group(artist, cleaned)
        if ok and entry is None and cleaned != album:
            ok, entry = self._search_release_group(artist, album)
        return ok, entry

    def _find_artist_mbid(self, artists):
        for name in artists:
            status, data = self._get("artist", {"query": f'artist:"{_lucene(name)}"', "limit": 2})
            if status != 200 or data is None:
                return False, None
            for hit in data.get("artists") or []:
                if (hit.get("score") or 0) >= MIN_SCORE:
                    return True, hit.get("id")
        return True, None

    def _lookup_artist(self, artists, mbid):
        if not mbid:
            ok, mbid = self._find_artist_mbid(artists)
            if not ok:
                return False, None
            if not mbid:
                return True, None
        status, data = self._get(f"artist/{mbid}", {"inc": "genres+tags+ratings"})
        if status == 404:
            return True, None
        if status != 200 or data is None:
            return False, None
        life = data.get("life-span") or {}
        extras = {}
        if data.get("type"):
            extras["artist_type"] = data["type"]
        if data.get("country"):
            extras["artist_country"] = data["country"]
        if life.get("begin"):
            extras["artist_begin"] = life["begin"][:4]
        if life.get("ended") is not None:
            extras["artist_ended"] = bool(life["ended"])
        return True, {
            "genres": _genres(data.get("genres")),
            "tags": clean_tags([t for t in data.get("tags") or [] if (t.get("count") or 0) > 0]),
            "extras": extras,
            "matched": (data.get("name") or "").lower() or None,
        }

    def _cached(self, section, key, lookup):
        """Return (hit, entry): cache first, else lookup (cached unless transient failure)."""
        cache = self.cache.section(section)
        if key in cache:
            self.stats["cache_hits"] += 1
            return True, cache[key]
        ok, entry = lookup()
        if ok:
            cache[key] = entry
            return True, entry
        self.stats["errors"] += 1
        return False, None

    def fetch(self, artist, track, album, isrc):
        enrichment = empty_enrichment(self.name)
        candidates = artist_candidates(artist)
        primary = _norm(candidates[0])
        mbid = None

        if isrc:
            _, entry = self._cached("track", isrc, lambda: self._lookup_track(isrc))
            if entry:
                mbid = entry.get("artist_mbid")
                enrichment["levels"]["track"] = _level(entry.get("genres") or [], entry.get("tags") or [])
                enrichment["matched"]["track"] = entry.get("matched")

        if album:
            _, entry = self._cached(
                "album", f"{primary}|{_norm(clean_album(album))}", lambda: self._lookup_album(candidates[0], album)
            )
            if entry:
                enrichment["levels"]["album"] = _level(entry.get("genres") or [], entry.get("tags") or [])
                enrichment["extras"].update(entry.get("extras") or {})
                enrichment["matched"]["album"] = entry.get("matched")

        if primary:
            _, entry = self._cached("artist", primary, lambda: self._lookup_artist(candidates, mbid))
            if entry:
                enrichment["levels"]["artist"] = _level(entry.get("genres") or [], entry.get("tags") or [])
                enrichment["extras"].update(entry.get("extras") or {})
                enrichment["matched"]["artist"] = entry.get("matched")
        return enrichment

    def flush(self):
        self.cache.flush()
