import os
import time

import requests

from enrichment import (
    JsonCache,
    Throttle,
    artist_candidates,
    clean_album,
    clean_tags,
    clean_track,
    empty_enrichment,
    http_get_json,
    primary_artist,
)

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
LASTFM_MIN_INTERVAL = 0.25  # <= 4 req/s
RATE_LIMIT_ERROR = 29
NOT_FOUND_ERROR = 6
MAX_RATE_LIMIT_RETRIES = 4

OK, NOT_FOUND, ERROR = "ok", "not_found", "error"
_UNKNOWN_ALBUMS = {"", "unknown", "unknown album", "[unknown]", "<unknown>"}


def _norm(s):
    return (s or "").strip().lower()


def _dedupe(names):
    out = []
    for n in names:
        n = (n or "").strip()
        if n and n not in out:
            out.append(n)
    return out


class Provider:
    """Last.fm crowd tags at track, album and artist level, plus artist listener stats."""

    name = "lastfm"

    def __init__(self, cache_dir=".", sleep=time.sleep):
        self.api_key = os.environ.get("LASTFM_API_KEY")
        if not self.api_key:
            raise SystemExit("LASTFM_API_KEY is not set (add it to .env)")
        self.cache = JsonCache(os.path.join(cache_dir, "lastfm_cache.json"))
        for section in ("artist", "album", "track"):
            self.cache.section(section)
        self.throttle = Throttle(LASTFM_MIN_INTERVAL)
        self.session = requests.Session()
        self._sleep = sleep
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0}

    # -- HTTP ---------------------------------------------------------------

    def _call(self, method, **params):
        """Return (OK, data) | (NOT_FOUND, None) | (ERROR, None)."""
        query = {"method": method, "api_key": self.api_key, "format": "json", "autocorrect": 1, **params}
        backoff = 2.0
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            self.stats["calls"] += 1
            status, data = http_get_json(
                self.session, LASTFM_URL, params=query, throttle=self.throttle, sleep=self._sleep
            )
            if isinstance(data, dict) and "error" in data:
                code = data["error"]
                if code == NOT_FOUND_ERROR:
                    return NOT_FOUND, None
                if code == RATE_LIMIT_ERROR and attempt < MAX_RATE_LIMIT_RETRIES:
                    self._sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue
                return ERROR, None
            if status == 404:
                return NOT_FOUND, None
            if status != 200 or not isinstance(data, dict):
                return ERROR, None
            return OK, data
        return ERROR, None

    @staticmethod
    def _tags(data):
        raw = (data.get("toptags") or {}).get("tag") or []
        if isinstance(raw, dict):
            raw = [raw]
        tags = [{"name": t.get("name"), "count": int(t.get("count") or 0)} for t in raw if isinstance(t, dict)]
        return clean_tags(tags)

    def _top_tags(self, method, candidates, **fixed):
        """Try each candidate in order. Returns (status, tags, matched_name)."""
        errored = False
        for key, value in candidates:
            status, data = self._call(method, **{key: value}, **fixed)
            if status == ERROR:
                errored = True
                continue
            if status == OK:
                tags = self._tags(data)
                if tags:
                    attr = (data.get("toptags") or {}).get("@attr") or {}
                    matched = attr.get("track") or attr.get("album") or attr.get("artist") or value
                    return OK, tags, _norm(matched)
        return (ERROR if errored else NOT_FOUND), [], None

    # -- lookups ------------------------------------------------------------

    def lookup_track(self, artist, track):
        titles = _dedupe([clean_track(track), track])
        cands = [(a, t) for a in artist_candidates(artist) for t in titles]
        errored = False
        for a, t in cands:
            status, tags, matched = self._top_tags("track.getTopTags", [("track", t)], artist=a)
            if status == OK:
                return OK, {"genres": [], "tags": tags, "matched": matched}
            errored = errored or status == ERROR
        return (ERROR if errored else NOT_FOUND), None

    def lookup_album(self, artist, album):
        if _norm(album) in _UNKNOWN_ALBUMS:
            return NOT_FOUND, None
        titles = _dedupe([clean_album(album), album])
        errored = False
        for a in artist_candidates(artist):
            status, tags, matched = self._top_tags("album.getTopTags", [("album", t) for t in titles], artist=a)
            if status == OK:
                return OK, {"genres": [], "tags": tags, "matched": matched}
            errored = errored or status == ERROR
        return (ERROR if errored else NOT_FOUND), None

    def lookup_artist(self, artist):
        errored = False
        for a in artist_candidates(artist):
            status, tags, matched = self._top_tags("artist.getTopTags", [("artist", a)])
            if status == ERROR:
                errored = True
                continue
            istatus, info = self._call("artist.getInfo", artist=a)
            if status == NOT_FOUND and istatus != OK:
                errored = errored or istatus == ERROR
                continue
            if istatus == ERROR:
                return ERROR, None
            extras = {}
            if istatus == OK:
                node = info.get("artist") or {}
                stats = node.get("stats") or {}
                for key, field in (("artist_listeners", "listeners"), ("artist_playcount", "playcount")):
                    try:
                        extras[key] = int(stats[field])
                    except (KeyError, TypeError, ValueError):
                        pass
                similar = (node.get("similar") or {}).get("artist") or []
                if isinstance(similar, dict):
                    similar = [similar]
                extras["similar_artists"] = [s["name"] for s in similar if s.get("name")][:5]
                matched = matched or _norm(node.get("name"))
            return OK, {"genres": [], "tags": tags, "matched": matched, "extras": extras}
        return (ERROR if errored else NOT_FOUND), None

    # -- contract -----------------------------------------------------------

    def _cached(self, section, key, lookup):
        cache = self.cache.section(section)
        if key in cache:
            self.stats["cache_hits"] += 1
            return cache[key]
        status, value = lookup()
        if status == ERROR:
            self.stats["errors"] += 1
            return None
        cache[key] = value  # None for genuine not-found
        return value

    def fetch(self, artist, track, album, isrc):
        enrichment = empty_enrichment(self.name)
        a = _norm(primary_artist(artist))
        raw = {
            "track": self._cached("track", f"{a}|{_norm(track)}", lambda: self.lookup_track(artist, track)),
            "album": self._cached("album", f"{a}|{_norm(album)}", lambda: self.lookup_album(artist, album)),
            "artist": self._cached("artist", a, lambda: self.lookup_artist(artist)),
        }
        for name, payload in raw.items():
            if payload is None:
                continue
            enrichment["levels"][name] = {"genres": payload.get("genres", []), "tags": payload.get("tags", [])}
            enrichment["matched"][name] = payload.get("matched")
            enrichment["extras"].update(payload.get("extras") or {})
        return enrichment

    def flush(self):
        self.cache.flush()
