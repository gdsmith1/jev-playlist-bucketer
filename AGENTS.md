# AGENTS.md

Operational notes for agents. User-facing setup and usage live in `README.md`; read the code for the rest.

## Where things are
All paths are relative to the repo root, which is also where commands must be run (caches and `runs/` use the working directory).

| Thing | Location | Notes |
|---|---|---|
| CLI entry point | `bucketer/__main__.py` | run as `python -m bucketer`; the CLI lives in `bucketer/cli.py` |
| Row loading, grouping, bucket output | `bucketer/pipeline.py` | |
| Run flow | `bucketer/cli.py` | pass 1: fetch Last.fm for every album, write the dashboard; real runs then choose buckets (`checkpoint.py`), confirm the spend, and pass 2 scores with jev; then write CSVs. `JevClient` is built after selection and never in dry runs |
| Bucket selection and spend check | `bucketer/checkpoint.py` | `suggest_buckets` turns dashboard clusters into buckets, `write_recommended`, `choose_buckets` (`--select`/`--buckets` or the questionary checklist plus custom-file prompt), `load_custom`, `confirm_spend` (`--yes` skips; no terminal without it exits) |
| jev client, question building, `FALLBACK_BUCKET` | `bucketer/jev.py` | uses the official `typesafe-sdk`; the only code that spends tokens; owns `jev_cache.json` |
| Last.fm client, `Throttle` | `bucketer/lastfm.py` | `requests` + urllib3 `Retry` for transport errors; owns `lastfm_cache.json` |
| Genre dashboard | `bucketer/dashboard/` | written on every run unless `--no-dashboard`, and rewritten after pass 2 on real runs: with `jev_result` it gains a "Your buckets" section (`static/sections/yourbuckets.js`, pure computation in `jevresults.py`: per-bucket counts, other, overlap, jev-vs-tag-fit agreement for recommended buckets, borderline scores within 0.25 below the threshold) and a per-album `jev` record shown as bars in the all-albums drill-down; without it the output is unchanged; `analysis.py` (pure `analyze`: clusters with label tags/cohesion/similar artists, outliers merged by artist with specific reasons, `album_records` per album), `quality.py` / `noise.py` / `decades.py` / `similar.py` (data-quality counts, tag noise audit with a small dashboard-only `NOISE_TAGS` list of uncertain tags; definite noise is dropped by `clean_tags` in `tags.py`, decade histograms, similar-artist neighbours of outliers), `render.py` (`render`, `write_dashboard`), `songs.py` (`song_dicts`: per-song dicts the CLI passes as `songs=` to `write_dashboard`/`analyze`; without it the Full playlist tab shows one row per album), `static/` (three tabs recommended/selected/playlist via `tabs.js`, URL hash; `page.html`, `style.css`, `app.js` helpers, one `sections/*.js` per page section, concatenated at render time) -> `runs/<ts>/dashboard.html`; no jev |
| Tag cleaning / name cleaning / jev text | `bucketer/tags.py`, `names.py`, `formatting.py` | `format_for_jev` is in `formatting.py` |
| JSON cache / data shapes | `bucketer/cache.py`, `models.py` | |
| Last.fm cache | `lastfm_cache.json` | sections `album` (`artist\|clean album`; entries also carry `cover`, `""` = none, fetched lazily for older entries) `artist` (primary artist; `extras.similar_full` = up to 30 `{name, match}`, fetched lazily only with `--similar`, `[]` = none found) and `tag` (`tag.getInfo` summary), lowercase keys; `null` = genuinely not found, errors are never cached |
| jev score cache | `jev_cache.json` | key = sha256 of bucket fingerprint + `\n` + the exact `format_for_jev` text; value `{label, scores, confidence, fingerprint}`. Legacy entries (key = sha256(text), no fingerprint) are lazily copied under the new key when their score keys equal the current bucket keys, never deleted |
| Run output | `runs/<timestamp>/<bucket>.csv` | one folder per run, including dry runs (empty) |
| Buckets | `runs/<ts>/recommended_buckets.json`, `runs/<ts>/selected_buckets.json`, `buckets.json` | recommended = all suggestions, written every run incl. dry runs; selected = what was scored, each with `source` (`recommended`/`custom`); `buckets.json` at the repo root is the suggested home for a user-owned custom file (`{key: {"description"}}`, loaded via the prompt or `--buckets`), never written by code, do not edit |
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
Other flags: `--limit N` (first N rows; **default is all rows**, so always pass `--dry-run`, `--sample` or `--limit` when testing), `--threshold X` (default 0.8), `--select all|none|a,b,c` and `--buckets PATH` (one of them is needed for real runs without a TTY), `--no-dashboard`, `--similar` (one extra Last.fm call per uncached artist for the dashboard's similar-artists section; never needed for tests), `--yes` (skips the confirmation; never pass it without owner approval), `--jev-cache PATH`, `--refresh-lastfm`, `--refresh-jev` (see README or `-h`). The `--refresh-*` flags replace the whole cache file with only the albums from that run, so back the file up first.

## Rules for working here
- **Never run `python -m bucketer` without `--dry-run` unless the user explicitly approves.** Real runs spend jev tokens (a 300-song sample is about 270 calls). Dry runs only call Last.fm, and cached entries make them nearly free.
- Changing `format_for_jev` output changes every jev cache key, so previously paid-for scores stop being reused. Do it deliberately and say so.
- Tag filtering in `clean_tags` is re-applied when reading the Last.fm cache, so filter changes need no cache clearing. Changing what gets *fetched* does.
- `other` is a built-in fallback bucket (`FALLBACK_BUCKET` in `bucketer/jev.py`), never sent to jev; a suggested bucket named `other` is renamed `other_genre`.
- `--sample N --seed S` picks the same rows every time for a given playlist; use seed 7 to compare against earlier runs.
- Tests: `poetry run python -m unittest discover tests` (offline). Add tests alongside new behavior.
- Last.fm is throttled to about 4 requests/s (`LASTFM_MIN_INTERVAL` in `bucketer/lastfm.py`); don't parallelize calls.
