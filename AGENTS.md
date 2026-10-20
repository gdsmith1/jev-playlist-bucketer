# AGENTS.md

Operational notes for agents. User-facing setup and usage live in `README.md`; read the code for the rest.

## Where things are
All paths are relative to the repo root, which is also where commands must be run (caches and `runs/` use the working directory).

| Thing | Location | Notes |
|---|---|---|
| CLI entry point | `bucketer/__main__.py` | run as `python -m bucketer`; the CLI lives in `bucketer/cli.py` |
| Row loading, grouping, bucket output | `bucketer/pipeline.py` | |
| Run flow | `bucketer/cli.py` | pass 1 fetch all Last.fm, dashboard (dry run), `select_buckets` seam (pass-through until DASH-11b), pass 2 jev scoring, write CSVs; `JevClient` is built after selection and never in dry runs |
| jev client, question building, `FALLBACK_BUCKET` | `bucketer/jev.py` | uses the official `typesafe-sdk`; the only code that spends tokens; owns `jev_cache.json` |
| Last.fm client, `Throttle` | `bucketer/lastfm.py` | `requests` + urllib3 `Retry` for transport errors; owns `lastfm_cache.json` |
| Genre dashboard | `bucketer/dashboard.py` | dry-run only; `analyze` (clusters, outliers) + `render` to `runs/<ts>/dashboard.html`; no jev; `--no-dashboard` skips |
| Tag cleaning / name cleaning / jev text | `bucketer/tags.py`, `names.py`, `formatting.py` | `format_for_jev` is in `formatting.py` |
| JSON cache / data shapes | `bucketer/cache.py`, `models.py` | |
| Last.fm cache | `lastfm_cache.json` | sections `album` (`artist\|clean album`; entries also carry `cover`, `""` = none, fetched lazily for older entries) `artist` (primary artist) and `tag` (`tag.getInfo` summary), lowercase keys; `null` = genuinely not found, errors are never cached |
| jev score cache | `jev_cache.json` | key = sha256 of bucket fingerprint + `\n` + the exact `format_for_jev` text; value `{label, scores, confidence, fingerprint}`. Legacy entries (key = sha256(text), no fingerprint) are lazily copied under the new key when their score keys equal the current bucket keys, never deleted |
| Run output | `runs/<timestamp>/<bucket>.csv` | one folder per run, including dry runs (empty) |
| Buckets | `buckets.json` | user-owned and not final; do not edit unless asked |
| Playlist input | `spotlistr-exported-playlist.csv` | local, gitignored |
| Secrets | `.env` | `LASTFM_API_KEY`, `TYPESAFE_API_KEY` |

`*.json`, `*.csv`, `runs/`, `.env` are gitignored, so none of the above data files show up in `git status`.

## Commands
Run from the repo root.
```
poetry install

# tests (offline: Last.fm session and jev SDK client are mocked)
poetry run python -m unittest discover tests
poetry run python -m unittest tests.test_tags                # one module
poetry run python -m unittest tests.test_lastfm.LastfmTest.test_error_not_cached   # one test

# safe run: Last.fm only, prints the jev input per album, no jev calls
poetry run python -m bucketer spotlistr-exported-playlist.csv --sample 300 --seed 7 --dry-run

# real run (spends jev tokens, needs explicit user approval)
poetry run python -m bucketer spotlistr-exported-playlist.csv --sample 300 --seed 7
```
Other flags: `--limit N` (first N rows; **default is all rows**, so always pass `--dry-run`, `--sample` or `--limit` when testing), `--threshold X` (default 1.0), `--buckets PATH`, `--jev-cache PATH`, `--refresh-lastfm`, `--refresh-jev` (see README or `-h`). The `--refresh-*` flags replace the whole cache file with only the albums from that run, so back the file up first.

## Rules for working here
- **Never run `python -m bucketer` without `--dry-run` unless the user explicitly approves.** Real runs spend jev tokens (a 300-song sample is about 270 calls). Dry runs only call Last.fm, and cached entries make them nearly free.
- Changing `format_for_jev` output changes every jev cache key, so previously paid-for scores stop being reused. Do it deliberately and say so.
- Tag filtering in `clean_tags` is re-applied when reading the Last.fm cache, so filter changes need no cache clearing. Changing what gets *fetched* does.
- `other` is a built-in fallback bucket (`FALLBACK_BUCKET` in `bucketer/jev.py`), never sent to jev; a bucket of that name in `buckets.json` is ignored.
- `--sample N --seed S` picks the same rows every time for a given playlist; use seed 7 to compare against earlier runs.
- Tests: `poetry run python -m unittest discover tests` (offline). Add tests alongside new behavior.
- Last.fm is throttled to about 4 requests/s (`LASTFM_MIN_INTERVAL` in `bucketer/lastfm.py`); don't parallelize calls.
