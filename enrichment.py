"""Shared helpers for metadata providers: throttling, caching, name/tag cleanup,
HTTP retry, and the text formatter that builds what jev receives. No provider
code and no network calls live here except through `http_get_json`."""

import json
import os
import re
import time
from collections import Counter

import requests

MAX_TAGS_PER_LEVEL = 8
MAX_ITEMS_PER_LEVEL = 6
MAX_TEXT_LEN = 600
LEVEL_ORDER = ("track", "album", "artist")

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

_YEAR_RE = re.compile(r"^\d{4}$")
_DECADE_RE = re.compile(r"^\d{2,4}s$")


class Throttle:
    """Ensures consecutive `wait()` calls are at least `min_interval` seconds apart."""

    def __init__(self, min_interval, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last = None

    def wait(self):
        if self._last is not None:
            elapsed = self._clock() - self._last
            if elapsed < self.min_interval:
                self._sleep(self.min_interval - elapsed)
        self._last = self._clock()


class JsonCache:
    """A dict persisted as JSON. Missing file -> empty cache."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def __contains__(self, key):
        return key in self.data

    def section(self, name):
        """Return the (created on demand) sub-dict `name`, e.g. cache.section("artist")."""
        return self.data.setdefault(name, {})

    def flush(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_ARTIST_SPLIT_RE = re.compile(r";\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+|\s+&\s+", re.IGNORECASE)

_TRAILING_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_TRACK_PAREN_RE = re.compile(
    r"\s*\((?:[^()]*\b)?(?:remaster(?:ed)?|live|feat\.?|ft\.?|featuring)\b[^()]*\)\s*$",
    re.IGNORECASE,
)
_TRACK_DASH_RE = re.compile(r"\s+-\s+(?:\d{4}\s+)?(?:remaster(?:ed)?|live)\b.*$", re.IGNORECASE)

_ALBUM_PAREN_RE = re.compile(
    r"\s*\([^()]*\b(?:deluxe|remaster(?:ed)?|expanded|edition|anniversary|bonus|version)\b[^()]*\)\s*$",
    re.IGNORECASE,
)
_ALBUM_DASH_RE = re.compile(
    r"\s+-\s+[^-]*\b(?:deluxe|remaster(?:ed)?|expanded|edition|anniversary|bonus|version)\b.*$",
    re.IGNORECASE,
)


def artist_candidates(s):
    """Lookup attempts in order: primary artist, then the full string if different."""
    full = (s or "").strip()
    primary = primary_artist(full)
    return [primary] if primary == full else [primary, full]


def primary_artist(s):
    s = (s or "").strip()
    parts = _ARTIST_SPLIT_RE.split(s, maxsplit=1)
    return parts[0].strip() or s


def _strip_repeatedly(s, patterns):
    original = (s or "").strip()
    current = original
    while True:
        previous = current
        for pattern in patterns:
            current = pattern.sub("", current).strip()
        if current == previous:
            break
    return current or original


def clean_track(s):
    """Strip trailing remaster/live/feat/bracket noise. A leading parenthetical is kept."""
    return _strip_repeatedly(s, [_TRAILING_BRACKET_RE, _TRACK_PAREN_RE, _TRACK_DASH_RE])


def clean_album(s):
    return _strip_repeatedly(s, [_TRAILING_BRACKET_RE, _ALBUM_PAREN_RE, _ALBUM_DASH_RE])


def clean_tags(tags, max_n=MAX_TAGS_PER_LEVEL):
    """Normalize `[{"name", "count"}]` (bare strings tolerated, count 0): lowercase,
    drop years/decades and noise, dedupe (best count wins), sort by count desc then
    name, truncate."""
    best = {}
    for tag in tags or []:
        if isinstance(tag, str):
            name, count = tag, 0
        else:
            name, count = tag.get("name"), tag.get("count") or 0
        if not name:
            continue
        name = name.strip().lower()
        if not name or name in NOISE_TAGS or _YEAR_RE.match(name) or _DECADE_RE.match(name):
            continue
        if name not in best or count > best[name]:
            best[name] = count
    ordered = sorted(best.items(), key=lambda item: (-item[1], item[0]))
    return [{"name": name, "count": count} for name, count in ordered[:max_n]]


# ---------------------------------------------------------------------------
# Enrichment shape, formatting, stats
# ---------------------------------------------------------------------------


def empty_enrichment(source):
    return {
        "source": source,
        "levels": {"track": None, "album": None, "artist": None},
        "extras": {},
        "matched": {"artist": None, "album": None, "track": None},
    }


def _level_items(level):
    if not level:
        return []
    items = []
    seen = set()
    names = [g.strip().lower() for g in level.get("genres") or [] if g]
    tags = sorted(
        level.get("tags") or [],
        key=lambda t: (-(t.get("count") or 0), t["name"].strip().lower()),
    )
    names += [t["name"].strip().lower() for t in tags]
    for name in names:
        if name and name not in seen:
            seen.add(name)
            items.append(name)
    return items[:MAX_ITEMS_PER_LEVEL]


def _info_parts(extras):
    e = extras or {}
    parts = []
    if e.get("artist_type") or e.get("artist_country"):
        kind = str(e.get("artist_type") or "artist").lower()
        parts.append(f"{kind} from {e['artist_country']}" if e.get("artist_country") else kind)
    if e.get("artist_begin"):
        began = f"began {e['artist_begin']}"
        parts.append(f"{began}, ended" if e.get("artist_ended") else began)
    if e.get("album_type"):
        secondary = [str(x).lower() for x in e.get("album_secondary") or []]
        text = f"release: {str(e['album_type']).lower()}"
        parts.append(f"{text} ({', '.join(secondary)})" if secondary else text)
    if e.get("first_release_date"):
        parts.append(f"first released {e['first_release_date']}")
    if e.get("format"):
        parts.append(f"format: {str(e['format']).lower()}")
    if e.get("year"):
        parts.append(f"released {e['year']}")
    if e.get("country") and not e.get("artist_country"):
        parts.append(f"country: {e['country']}")
    if e.get("have") is not None:
        parts.append(f"{e['have']} collectors")
    if e.get("want") is not None:
        parts.append(f"{e['want']} wanted")
    if e.get("artist_listeners") is not None:
        parts.append(f"{e['artist_listeners']} listeners")
    similar = e.get("similar_artists") or []
    if similar:
        parts.append("similar: " + ", ".join(str(a) for a in similar[:5]))
    return parts


def format_for_jev(fields, enrichment):
    """Deterministic text sent to jev (and used as its cache key). See PLAN.md 3.5."""
    artist, track, album, release_date, length = fields[:5]
    levels = enrichment.get("levels") or {}
    items = {name: _level_items(levels.get(name)) for name in LEVEL_ORDER}
    occurrences = Counter(item for name in LEVEL_ORDER for item in items[name])

    seen = set()
    sections = []
    for name in LEVEL_ORDER:
        if not items[name]:
            body = "no data"
        else:
            shown = []
            for item in items[name]:
                if item in seen:
                    continue
                seen.add(item)
                shown.append(f"{item} (x{occurrences[item]})" if occurrences[item] > 1 else item)
            body = ", ".join(shown) if shown else "same as higher level"
        sections.append(f"{name}: {body}")

    head = f"{artist}, {track}, {album}, {release_date}, {length}"
    base = " | ".join([head] + sections)

    parts = _info_parts(enrichment.get("extras"))
    while parts:
        text = f"{base} | info: {'; '.join(parts)}"
        if len(text) <= MAX_TEXT_LEN:
            return text
        parts.pop()
    return base


def _has_data(level):
    return bool(level) and bool(level.get("genres") or level.get("tags"))


def coverage_stats(enrichments):
    stats = {"songs": 0, "track": 0, "album": 0, "artist": 0, "any": 0, "none": 0}
    for enrichment in enrichments:
        stats["songs"] += 1
        hits = [_has_data((enrichment.get("levels") or {}).get(name)) for name in LEVEL_ORDER]
        for name, hit in zip(LEVEL_ORDER, hits):
            stats[name] += hit
        if any(hits):
            stats["any"] += 1
        else:
            stats["none"] += 1
    return stats


def format_run_stats(source, coverage, provider_stats, elapsed):
    n = coverage["songs"]
    return (
        f"{source} level coverage over {n} songs: track {coverage['track']}/{n}  "
        f"album {coverage['album']}/{n}  artist {coverage['artist']}/{n}  "
        f"any {coverage['any']}/{n}  none {coverage['none']}/{n}\n"
        f"{source} calls: {provider_stats.get('calls', 0)}  "
        f"cache_hits: {provider_stats.get('cache_hits', 0)}  "
        f"errors: {provider_stats.get('errors', 0)}   elapsed: {elapsed:.0f}s"
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER = 120.0


def http_get_json(
    client,
    url,
    *,
    params=None,
    headers=None,
    throttle=None,
    max_retries=4,
    timeout=20,
    sleep=time.sleep,
):
    """GET `url` and return `(status_code, parsed_json_or_None)`. Never raises for
    network problems: retries 429/5xx/timeouts/connection errors with exponential
    backoff (1, 2, 4, 8s, capped at 30s, `Retry-After` honored), then gives up with
    the last status (0 if there was no response). Non-retryable statuses (404...)
    are returned immediately."""
    backoff = 1.0
    status = 0
    for attempt in range(max_retries + 1):
        if throttle is not None:
            throttle.wait()
        retry_after = None
        try:
            resp = client.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException:
            status = 0
        else:
            status = resp.status_code
            if status not in _RETRY_STATUSES:
                try:
                    return status, resp.json()
                except ValueError:
                    return status, None
            try:
                retry_after = float(resp.headers.get("Retry-After"))
            except (TypeError, ValueError):
                retry_after = None
        if attempt == max_retries:
            break
        delay = min(retry_after, _MAX_RETRY_AFTER) if retry_after is not None else backoff
        sleep(delay)
        backoff = min(backoff * 2, 30.0)
    return status, None
