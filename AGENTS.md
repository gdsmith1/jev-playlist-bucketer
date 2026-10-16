# AGENTS.md

Operational notes for agents. User-facing setup and usage live in `README.md`; read the code for the rest.

## Where things are
All paths are relative to the repo root, which is also where commands must be run (caches and `runs/` use the working directory).

| Thing | Location | Notes |
|---|---|---|
| CLI entry point | `categorize.py` | grouping, jev request, bucket CSV output |
| Tag cleaning, `format_for_jev`, throttle, cache class, HTTP retry | `enrichment.py` | no provider code |
| Last.fm provider | `providers/lastfm.py` | the only provider; `providers/__init__.py` is empty |
| Last.fm cache | `lastfm_cache.json` | sections `album` (`artist\|clean album`) and `artist` (primary artist), lowercase keys; `null` = genuinely not found, errors are never cached |
| jev score cache | `jev_cache.json` | key = sha256 of the exact `format_for_jev` text; value `{label, scores, confidence}` |
| Run output | `runs/<timestamp>/<bucket>.csv` | one folder per run, including dry runs (empty) |
| Buckets | `buckets.json` | user-owned and not final; do not edit unless asked |
| Playlist input | `spotlistr-exported-playlist.csv` | local, gitignored |
| Secrets | `.env` | `LASTFM_API_KEY`, `TYPESAFE_API_KEY` |

`*.json`, `*.csv`, `runs/`, `.env` are gitignored, so none of the above data files show up in `git status`.

## Commands
Run from the repo root.
```
poetry install

# tests (offline, mocked HTTP)
poetry run python -m unittest discover tests
poetry run python -m unittest tests.test_enrichment          # one module
poetry run python -m unittest tests.test_lastfm.LastfmTest.test_error_not_cached   # one test

# safe run: Last.fm only, prints the jev input per album, no jev calls
poetry run python categorize.py spotlistr-exported-playlist.csv --sample 300 --seed 7 --dry-run

# real run (spends jev tokens, needs explicit user approval)
poetry run python categorize.py spotlistr-exported-playlist.csv --sample 300 --seed 7
```
Other flags: `--limit N` (first N rows, default 40), `--threshold X` (default 1.0).

## Rules for working here
- **Never run `categorize.py` without `--dry-run` unless the user explicitly approves.** Real runs spend jev tokens (a 300-song sample is about 270 calls). Dry runs only call Last.fm, and cached entries make them nearly free.
- Changing `format_for_jev` output changes every jev cache key, so previously paid-for scores stop being reused. Do it deliberately and say so.
- Tag filtering in `clean_tags` is re-applied when reading the Last.fm cache, so filter changes need no cache clearing. Changing what gets *fetched* does.
- `other` is a built-in fallback bucket (`FALLBACK_BUCKET` in `categorize.py`), never sent to jev; a bucket of that name in `buckets.json` is ignored.
- `--sample N --seed S` picks the same rows every time for a given playlist; use seed 7 to compare against earlier runs.
- Tests: `poetry run python -m unittest discover tests` (offline, mocked HTTP). Add tests alongside new behavior.
- Last.fm is throttled to about 4 requests/s (`LASTFM_MIN_INTERVAL`); don't parallelize calls.
