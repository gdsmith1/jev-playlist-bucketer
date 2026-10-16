"""Shared helpers for metadata providers: throttling, caching, name/tag cleanup,
HTTP retry, and the text formatter that builds what jev receives. No provider
code and no network calls live here except through `http_get_json`."""

import json
import os
import re
import time

import requests

MAX_TAGS_PER_LEVEL = 8
MAX_ITEMS_PER_LEVEL = 6
MAX_TEXT_LEN = 600
LEVEL_ORDER = ("album", "artist")
UNKNOWN_ALBUMS = frozenset({"", "unknown", "unknown album", "[unknown]", "<unknown>"})

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

_YEAR_RE = re.compile(r"^\d{4}$")
_DECADE_RE = re.compile(r"^\d{2,4}s$")
# List-membership and chatter tags: "1001 albums you must hear...", "best of 2013", "top metal albums of
# the decade", "allboutguitarcom", and jokes like "a good girlfriend will have sex with me to this music".
_JUNK_RE = re.compile(
    r"^(wrong|incorrect|best of|top )\b|\balbums? (you|i|of|that)\b|\bgirlfriend\b|\b\d{4}\b.*\b\d{4}\b|\w+com$"
)


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

_ALBUM_PAREN_RE = re.compile(
    r"\s*\([^()]*\b(?:deluxe|remaster(?:ed)?|reissue|expanded|edition|anniversary|bonus|version)\b[^()]*\)\s*$",
    re.IGNORECASE,
)
_ALBUM_DASH_RE = re.compile(
    r"\s+-\s+[^-]*\b(?:deluxe|remaster(?:ed)?|reissue|expanded|edition|anniversary|bonus|version)\b.*$",
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


def clean_album(s):
    return _strip_repeatedly(s, [_TRAILING_BRACKET_RE, _ALBUM_PAREN_RE, _ALBUM_DASH_RE])


def tag_key(name):
    """Spelling-insensitive identity: `synth-pop`, `synth pop` and `synthpop` match."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _tag_order(name, count):
    return (name in VAGUE_TAGS, -count, name)


def clean_tags(tags, max_n=MAX_TAGS_PER_LEVEL, exclude=()):
    """Normalize `[{"name", "count"}]` (bare strings tolerated, count 0): lowercase,
    drop years/decades, noise, junk and echoes of `exclude` names (artist/album),
    merge spelling variants (best count wins), sort specific tags first then by
    count desc then name, truncate."""
    excluded = {tag_key(n) for n in exclude if n}
    best = {}
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
            or _YEAR_RE.match(name)
            or _DECADE_RE.match(name)
            or tag_key(name) in excluded
        ):
            continue
        key = tag_key(name)
        if key not in best or (count, name) > (best[key][1], best[key][0]):
            best[key] = (name, count)
    ordered = sorted(best.values(), key=lambda item: _tag_order(*item))
    return [{"name": name, "count": count} for name, count in ordered[:max_n]]


# ---------------------------------------------------------------------------
# Enrichment shape, formatting, stats
# ---------------------------------------------------------------------------


def empty_enrichment(source):
    return {
        "source": source,
        "levels": {"album": None, "artist": None},
        "extras": {},
        "matched": {"artist": None, "album": None},
    }


def is_unknown_album(album):
    return (album or "").strip().lower() in UNKNOWN_ALBUMS


def _level_items(level):
    if not level:
        return []
    names = [g.strip().lower() for g in level.get("genres") or [] if g]
    tags = sorted(
        level.get("tags") or [],
        key=lambda t: _tag_order(t["name"].strip().lower(), t.get("count") or 0),
    )
    names += [t["name"].strip().lower() for t in tags]
    items = []
    for name in names:
        if name and name not in items:
            items.append(name)
    return items[:MAX_ITEMS_PER_LEVEL]


def format_for_jev(artist, album, release_date, enrichment):
    """Deterministic album-level text sent to jev (and used as its cache key).
    Semantic evidence only: no counts, track titles, durations or ids."""
    artist = primary_artist(artist)
    year = (release_date or "").strip()[:4]
    if is_unknown_album(album):
        head = f"Artist: {artist}"
    else:
        head = f"Album: {clean_album(album)} by {artist}" + (f" ({year})" if _YEAR_RE.match(year) else "")

    levels = enrichment.get("levels") or {}
    seen = set()
    lines = [head]
    for name in LEVEL_ORDER:
        shown = [item for item in _level_items(levels.get(name)) if item not in seen]
        seen.update(shown)
        if shown:
            lines.append(f"{name.capitalize()} tags (strongest first): {', '.join(shown)}")

    similar = (enrichment.get("extras") or {}).get("similar_artists") or []
    while True:
        out = lines + ([f"Similar artists: {', '.join(str(a) for a in similar)}"] if similar else [])
        text = "\n".join(out)
        if len(text) <= MAX_TEXT_LEN or not similar:
            return text
        similar = similar[:-1]


def _has_data(level):
    return bool(level) and bool(level.get("genres") or level.get("tags"))


def coverage_stats(enrichments):
    stats = {"albums": 0, "album": 0, "artist": 0, "any": 0, "none": 0}
    for enrichment in enrichments:
        stats["albums"] += 1
        hits = [_has_data((enrichment.get("levels") or {}).get(name)) for name in LEVEL_ORDER]
        for name, hit in zip(LEVEL_ORDER, hits):
            stats[name] += hit
        if any(hits):
            stats["any"] += 1
        else:
            stats["none"] += 1
    return stats


def format_run_stats(source, coverage, provider_stats, elapsed):
    n = coverage["albums"]
    return (
        f"{source} coverage over {n} albums: album {coverage['album']}/{n}  "
        f"artist {coverage['artist']}/{n}  any {coverage['any']}/{n}  none {coverage['none']}/{n}\n"
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
