import os

import requests

from enrichment import JsonCache, Throttle, clean_tags, empty_enrichment, http_get_json

MB_USER_AGENT = "jev-playlist-bucketer/0.1 ( gibson.smith@liatrio.com )"
MB_MIN_INTERVAL = 1.0  # seconds between MusicBrainz requests
MB_BASE = "https://musicbrainz.org/ws/2"


class Provider:
    """Baseline: recording-level genres/tags via ISRC. Album/artist levels stay None."""

    name = "musicbrainz"

    def __init__(self, cache_dir="."):
        self.cache = JsonCache(os.path.join(cache_dir, "musicbrainz_cache.json"))
        for section in ("artist", "album", "track"):
            self.cache.section(section)
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

    def _lookup_track(self, isrc):
        """Return (ok, level). ok=False means a transient failure (do not cache)."""
        status, data = self._get(f"isrc/{isrc}", {"inc": "tags+artist-credits"})
        if status == 404:
            return True, None
        if status != 200 or data is None:
            return False, None
        recordings = data.get("recordings") or []
        if not recordings:
            return True, None

        status, recording = self._get(
            f"recording/{recordings[0]['id']}", {"inc": "genres+tags+artist-credits"}
        )
        if status != 200 or recording is None:
            return False, None

        genres = []
        for genre in recording.get("genres") or []:
            name = (genre.get("name") or "").strip().lower()
            if name and name not in genres:
                genres.append(name)
        tags = clean_tags([t for t in recording.get("tags") or [] if (t.get("count") or 0) > 0])
        if not genres and not tags:
            return True, None
        return True, {"genres": genres, "tags": tags}

    def fetch(self, artist, track, album, isrc):
        enrichment = empty_enrichment(self.name)
        if not isrc:
            return enrichment

        track_cache = self.cache.section("track")
        if isrc in track_cache:
            self.stats["cache_hits"] += 1
            enrichment["levels"]["track"] = track_cache[isrc]
            return enrichment

        ok, level = self._lookup_track(isrc)
        if ok:
            track_cache[isrc] = level
            enrichment["levels"]["track"] = level
        else:
            self.stats["errors"] += 1
        return enrichment

    def flush(self):
        self.cache.flush()
