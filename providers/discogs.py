import difflib
import os
import re
import time

import requests

from enrichment import (
    JsonCache,
    Throttle,
    clean_album,
    clean_track,
    empty_enrichment,
    http_get_json,
    primary_artist,
)

USER_AGENT = "jev-playlist-bucketer/0.1 ( gibson.smith@liatrio.com )"
BASE = "https://api.discogs.com"
MIN_INTERVAL = 1.1
RESET_WAIT = 60.0
MAX_CALLS_PER_SONG = 3
NOISE_FIELDS = ("barcode", "label", "thumb", "cover_image", "user_data")
FORMAT_KINDS = ("Album", "EP", "Single")

_PAREN_NUM_RE = re.compile(r"\s*\(\d+\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def norm(s):
    s = _PAREN_NUM_RE.sub("", (s or "").lower())
    return _NON_ALNUM_RE.sub(" ", s).strip()


def title_matches(result_title, artist, album, threshold=0.85):
    """Discogs titles look like "Artist - Album"; compare ignoring case/punctuation."""
    want = norm(f"{artist} - {album}")
    got = norm(result_title)
    if not want or not got:
        return False
    return got == want or difflib.SequenceMatcher(None, got, want).ratio() >= threshold


def strip_noise(result):
    return {k: v for k, v in result.items() if k not in NOISE_FIELDS}


def genres_of(result):
    """styles first (more specific), then genres; lowercase, deduped."""
    out = []
    for name in list(result.get("style") or []) + list(result.get("genre") or []):
        name = (name or "").strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def union_genres(results):
    out = []
    for r in results:
        for g in genres_of(r):
            if g not in out:
                out.append(g)
    return out


def format_kind(result):
    for f in result.get("format") or []:
        if f in FORMAT_KINDS:
            return f
    return None


def extras_of(result):
    community = result.get("community") or {}
    extras = {}
    year = str(result.get("year") or "")
    if year.isdigit():
        extras["year"] = int(year)
    if result.get("country"):
        extras["country"] = result["country"]
    if community.get("have") is not None:
        extras["have"] = community["have"]
    if community.get("want") is not None:
        extras["want"] = community["want"]
    kind = format_kind(result)
    if kind:
        extras["format"] = kind
    return extras


class _HeaderRecorder:
    """Session adapter: records the last response headers and, on a 429, waits
    RESET_WAIT seconds once and retries."""

    def __init__(self, session, sleep=time.sleep):
        self.session = session
        self.sleep = sleep
        self.headers = {}

    def get(self, url, **kwargs):
        resp = self.session.get(url, **kwargs)
        if resp.status_code == 429:
            self.headers = dict(resp.headers or {})
            self.sleep(RESET_WAIT)
            resp = self.session.get(url, **kwargs)
        self.headers = dict(resp.headers or {})
        return resp


class Provider:
    name = "discogs"

    def __init__(self, cache_dir=".", session=None, sleep=time.sleep):
        token = os.environ.get("DISCOGS_TOKEN")
        if not token:
            raise SystemExit("DISCOGS_TOKEN is not set (add it to .env)")
        self._headers = {"Authorization": f"Discogs token={token}", "User-Agent": USER_AGENT}
        self.cache = JsonCache(os.path.join(cache_dir, "discogs_cache.json"))
        for section in ("artist", "album", "track"):
            self.cache.section(section)
        self.sleep = sleep
        self.throttle = Throttle(MIN_INTERVAL, sleep=sleep)
        self.client = _HeaderRecorder(session or requests.Session(), sleep=sleep)
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0}
        self._song_calls = 0

    # -- HTTP ---------------------------------------------------------------

    def _search(self, params):
        """Return (ok, results). ok=False on transient failure (not cacheable)."""
        remaining = self.client.headers.get("X-Discogs-Ratelimit-Remaining")
        try:
            if remaining is not None and int(remaining) <= 1:
                self.sleep(RESET_WAIT)
                self.client.headers = {}
        except ValueError:
            pass
        self.stats["calls"] += 1
        self._song_calls += 1
        status, data = http_get_json(
            self.client,
            f"{BASE}/database/search",
            params=params,
            headers=self._headers,
            throttle=self.throttle,
            sleep=self.sleep,
        )
        if status != 200 or not isinstance(data, dict):
            return (status == 404), []
        return True, [strip_noise(r) for r in data.get("results") or []]

    # -- levels -------------------------------------------------------------

    def _lookup_album(self, artist, album):
        ok, results = self._search(
            {"type": "master", "artist": artist, "release_title": album, "per_page": 5}
        )
        if not ok:
            return False, None
        for r in results:
            genres = genres_of(r)
            if title_matches(r.get("title"), artist, album) and genres:
                return True, {
                    "genres": genres, "tags": [], "extras": extras_of(r), "matched": r["title"].lower()
                }
        ok, results = self._search(
            {"type": "release", "artist": artist, "release_title": album, "per_page": 5}
        )
        if not ok:
            return False, None
        matching = [r for r in results if title_matches(r.get("title"), artist, album)][:3]
        genres = union_genres(matching)
        if not genres:
            return True, None
        extras = extras_of(matching[0])
        for r in matching:
            if format_kind(r):
                extras["format"] = format_kind(r)
                break
        return True, {
            "genres": genres, "tags": [], "extras": extras, "matched": matching[0]["title"].lower()
        }

    def _lookup_artist(self, artist):
        ok, results = self._search({"type": "master", "artist": artist, "per_page": 10})
        if not ok:
            return False, None
        counts = {}
        used = 0
        for r in results:
            if norm(artist) != norm((r.get("title") or "").split(" - ")[0]):
                continue
            used += 1
            for g in genres_of(r):
                counts[g] = counts.get(g, 0) + 1
        if not counts:
            return True, None
        order = {g: i for i, g in enumerate(counts)}
        top = sorted(counts, key=lambda g: (-counts[g], order[g]))[:5]
        return True, {"genres": top, "tags": [], "extras": {}, "matched": norm(artist)}

    def _lookup_track(self, artist, track, album):
        ok, results = self._search(
            {"type": "release", "artist": artist, "track": track, "per_page": 5}
        )
        if not ok:
            return False, None
        nt, na = norm(track), norm(album)
        for r in results:
            title = r.get("title") or ""
            artist_part, _, name = title.partition(" - ")
            if norm(artist_part) != norm(artist) or not genres_of(r):
                continue
            nn = norm(name)
            plausible = (nt and nt in nn) or (na and (na in nn or nn in na) and nn)
            if plausible:
                return True, {"genres": genres_of(r), "tags": [], "extras": {}, "matched": title.lower()}
        return True, None

    # -- cached wrappers ----------------------------------------------------

    def _cached(self, section, key, fn):
        """Return (value, hit). Caches successes and genuine not-found; not errors."""
        cache = self.cache.section(section)
        if key in cache:
            self.stats["cache_hits"] += 1
            return cache[key]
        ok, value = fn()
        if ok:
            cache[key] = value
            return value
        self.stats["errors"] += 1
        return None

    def fetch(self, artist, track, album, isrc):
        enrichment = empty_enrichment(self.name)
        self._song_calls = 0
        main_artist = primary_artist(artist)
        cleaned_album = clean_album(album) if album else ""
        cleaned_track = clean_track(track) if track else ""

        if cleaned_album:
            key = f"{norm(main_artist)}|{norm(cleaned_album)}"
            value = self._cached("album", key, lambda: self._lookup_album(main_artist, cleaned_album))
            if value:
                enrichment["levels"]["album"] = {"genres": value["genres"], "tags": value["tags"]}
                enrichment["extras"].update(value.get("extras") or {})
                enrichment["matched"]["album"] = value.get("matched")

        if main_artist:
            value = self._cached("artist", norm(main_artist), lambda: self._lookup_artist(main_artist))
            if value:
                enrichment["levels"]["artist"] = {"genres": value["genres"], "tags": value["tags"]}
                enrichment["matched"]["artist"] = value.get("matched")

        if cleaned_track and main_artist and self._song_calls < MAX_CALLS_PER_SONG:
            key = f"{norm(main_artist)}|{norm(cleaned_track)}"
            value = self._cached(
                "track", key, lambda: self._lookup_track(main_artist, cleaned_track, cleaned_album)
            )
            if value:
                enrichment["levels"]["track"] = {"genres": value["genres"], "tags": value["tags"]}
                enrichment["matched"]["track"] = value.get("matched")
        return enrichment

    def flush(self):
        self.cache.flush()
