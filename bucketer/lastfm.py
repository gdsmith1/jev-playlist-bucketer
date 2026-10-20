"""Last.fm client: crowd tags at album and artist level, plus similar artists, cached on disk."""

import html
import os
import re
import time
from typing import Any, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache import JsonCache
from .models import Enrichment
from .names import artist_candidates, clean_album, is_unknown_album, primary_artist
from .tags import clean_tags

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
LASTFM_MIN_INTERVAL = 0.25  # <= 4 req/s
RATE_LIMIT_ERROR = 29
NOT_FOUND_ERROR = 6
MAX_RATE_LIMIT_RETRIES = 4

HTTP_TIMEOUT = 20
# Transport-level retries (429/5xx/connection errors, Retry-After honored) are urllib3's job.
HTTP_RETRY = Retry(total=4, backoff_factor=1.0, backoff_max=30, status_forcelist=(429, 500, 502, 503, 504), raise_on_status=False)

OK, NOT_FOUND, ERROR = "ok", "not_found", "error"


class Throttle:
    """Ensures consecutive `wait()` calls are at least `min_interval` seconds apart."""

    def __init__(self, min_interval: float, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            elapsed = self._clock() - self._last
            if elapsed < self.min_interval:
                self._sleep(self.min_interval - elapsed)
        self._last = self._clock()


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


_HTML_TAG = re.compile(r"<[^>]+>")
TAG_SUMMARY_MAX = 400
PLACEHOLDER_IMAGE_ID = "2a96cbd8b46e442fc41c2b86b821562f"  # Last.fm's grey default art, same for every missing cover
SIMILAR_LIMIT = 30
COVER_SIZES = ("extralarge", "large", "medium")


def clean_wiki(summary: str | None) -> str:
    """Last.fm wiki summaries carry anchor tags and a trailing 'Read more' link; return plain, shortened text."""
    text = html.unescape(_HTML_TAG.sub("", summary or ""))
    text = re.sub(r"\s*Read more on Last\.fm\.?\s*$", "", " ".join(text.split()))
    if len(text) > TAG_SUMMARY_MAX:
        text = text[:TAG_SUMMARY_MAX].rsplit(" ", 1)[0] + "…"
    return text


def _dedupe(names: list[str | None]) -> list[str]:
    out: list[str] = []
    for n in names:
        n = (n or "").strip()
        if n and n not in out:
            out.append(n)
    return out


class LastfmClient:
    def __init__(self, cache_dir: str = ".", sleep: Callable[[float], None] = time.sleep, refresh: bool = False) -> None:
        self.api_key = os.environ.get("LASTFM_API_KEY")
        if not self.api_key:
            raise SystemExit("LASTFM_API_KEY is not set (add it to .env)")
        self.cache = JsonCache(os.path.join(cache_dir, "lastfm_cache.json"), fresh=refresh)
        for section in ("artist", "album", "tag"):
            self.cache.section(section)
        self.throttle = Throttle(LASTFM_MIN_INTERVAL)
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=HTTP_RETRY))
        self._sleep = sleep
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0}

    # -- HTTP ---------------------------------------------------------------

    def _get_json(self, query: dict) -> tuple[int, Any]:
        """GET one Last.fm API call, throttled. Returns (status, parsed JSON or None); never raises for network problems (status 0)."""
        self.throttle.wait()
        try:
            resp = self.session.get(LASTFM_URL, params=query, timeout=HTTP_TIMEOUT)
        except requests.RequestException:
            return 0, None
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, None

    def _call(self, method: str, **params: Any) -> tuple[str, dict | None]:
        """Return (OK, data) | (NOT_FOUND, None) | (ERROR, None)."""
        query = {"method": method, "api_key": self.api_key, "format": "json", "autocorrect": 1, **params}
        backoff = 2.0
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            self.stats["calls"] += 1
            status, data = self._get_json(query)
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
    def _tags(data: dict, exclude: tuple = ()) -> list[dict]:
        raw = (data.get("toptags") or {}).get("tag") or []
        if isinstance(raw, dict):
            raw = [raw]
        tags = [{"name": t.get("name"), "count": int(t.get("count") or 0)} for t in raw if isinstance(t, dict)]
        return clean_tags(tags, exclude=exclude)

    def _top_tags(self, method: str, candidates: list[tuple[str, str]], exclude: tuple = (), **fixed: Any) -> tuple[str, list[dict]]:
        """Try each candidate in order. Returns (status, tags).
        `exclude` names (artist/album) are dropped from the tags as echoes."""
        errored = False
        for key, value in candidates:
            status, data = self._call(method, **{key: value}, **fixed)
            if status == ERROR:
                errored = True
                continue
            if status == OK:
                tags = self._tags(data, exclude)
                if tags:
                    return OK, tags
        return (ERROR if errored else NOT_FOUND), []

    # -- lookups ------------------------------------------------------------

    def lookup_album(self, artist: str, album: str) -> tuple[str, dict | None]:
        if is_unknown_album(album):
            return NOT_FOUND, None
        titles = _dedupe([clean_album(album), album])
        errored = False
        for a in artist_candidates(artist):
            status, tags = self._top_tags(
                "album.getTopTags", [("album", t) for t in titles], exclude=(a, album, clean_album(album)), artist=a
            )
            if status == OK:
                return OK, {"tags": tags}
            errored = errored or status == ERROR
        return (ERROR if errored else NOT_FOUND), None

    def lookup_artist(self, artist: str) -> tuple[str, dict | None]:
        errored = False
        for a in artist_candidates(artist):
            status, tags = self._top_tags("artist.getTopTags", [("artist", a)], exclude=(a,))
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
                similar = (node.get("similar") or {}).get("artist") or []
                if isinstance(similar, dict):
                    similar = [similar]
                extras["similar_artists"] = [s["name"] for s in similar if s.get("name")][:5]
            return OK, {"tags": tags, "extras": extras}
        return (ERROR if errored else NOT_FOUND), None

    def lookup_similar(self, artist: str, limit: int = SIMILAR_LIMIT) -> tuple[str, list[dict]]:
        status, data = self._call("artist.getSimilar", artist=artist, limit=limit)
        if status != OK:
            return status, []
        raw = (data.get("similarartists") or {}).get("artist") or []
        if isinstance(raw, dict):
            raw = [raw]
        return OK, [{"name": s["name"], "match": round(float(s.get("match") or 0), 4)} for s in raw if isinstance(s, dict) and s.get("name")]

    @staticmethod
    def _cover_url(data: dict) -> str:
        images = (data.get("album") or {}).get("image") or []
        by_size = {i.get("size"): i.get("#text") for i in images if isinstance(i, dict)}
        for size in COVER_SIZES:
            url = by_size.get(size) or ""
            if url and PLACEHOLDER_IMAGE_ID not in url:
                return url
        return ""

    def lookup_cover(self, artist: str, album: str) -> tuple[str, str]:
        """(status, url). url is "" when Last.fm knows the album but has no art."""
        if is_unknown_album(album):
            return NOT_FOUND, ""
        errored = False
        for a in artist_candidates(artist):
            for title in _dedupe([clean_album(album), album]):
                status, data = self._call("album.getInfo", artist=a, album=title)
                if status == ERROR:
                    errored = True
                elif status == OK:
                    url = self._cover_url(data)
                    if url:
                        return OK, url
        return (ERROR if errored else NOT_FOUND), ""

    def lookup_tag(self, name: str) -> tuple[str, dict | None]:
        status, data = self._call("tag.getInfo", tag=name)
        if status != OK:
            return status, None
        node = data.get("tag") or {}
        return OK, {
            "summary": clean_wiki((node.get("wiki") or {}).get("summary")),
            "reach": int(node.get("reach") or 0),
            "taggings": int(node.get("total") or 0),
        }

    # -- public -------------------------------------------------------------

    def _cached(self, section: str, key: str, lookup: Callable[[], tuple[str, dict | None]]) -> dict | None:
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

    def _cover_for(self, payload: dict, artist: str, album: str) -> str | None:
        """Cover URL stored on the album cache entry; fetched once and remembered ("" = none found). Errors leave it unset."""
        if "cover" not in payload:
            status, url = self.lookup_cover(artist, album)
            if status == ERROR:
                self.stats["errors"] += 1
                return None
            payload["cover"] = url
        else:
            self.stats["cache_hits"] += 1
        return payload["cover"] or None

    def fetch(self, artist: str, album: str, similar: bool = False) -> Enrichment:
        a = _norm(primary_artist(artist))
        album_payload = self._cached("album", f"{a}|{_norm(clean_album(album))}", lambda: self.lookup_album(artist, album))
        artist_payload = self._cached("artist", a, lambda: self.lookup_artist(artist))
        enrichment = Enrichment()
        if album_payload is not None:
            enrichment.cover = self._cover_for(album_payload, artist, album)
        # Re-clean on read so filter improvements also apply to tags cached earlier.
        if album_payload is not None:
            exclude = (artist, primary_artist(artist), album, clean_album(album))
            enrichment.album_tags = clean_tags(album_payload.get("tags", []), exclude=exclude)
        if artist_payload is not None:
            enrichment.artist_tags = clean_tags(artist_payload.get("tags", []), exclude=(artist, primary_artist(artist)))
            extras = artist_payload.get("extras") or {}
            enrichment.similar_artists = list(extras.get("similar_artists") or [])
            enrichment.similar_full = self.similar_artists(artist) if similar else list(extras.get("similar_full") or [])
        return enrichment

    def similar_artists(self, artist: str) -> list[dict]:
        """Up to SIMILAR_LIMIT [{name, match}] for an artist, stored on its artist cache entry (extras.similar_full); fetched lazily, errors not cached."""
        key = _norm(primary_artist(artist))
        payload = self.cache.section("artist").get(key)
        if payload is None:
            return []
        extras = payload.setdefault("extras", {})
        if "similar_full" not in extras:
            status, similar = self.lookup_similar(key)
            if status == ERROR:
                self.stats["errors"] += 1
                return []
            extras["similar_full"] = similar
        else:
            self.stats["cache_hits"] += 1
        return extras["similar_full"]

    def tag_info(self, name: str) -> dict | None:
        """Description and usage stats for one tag (None if unknown). Cached under `tag`."""
        return self._cached("tag", _norm(name), lambda: self.lookup_tag(name))

    def flush(self) -> None:
        self.cache.flush()
