# jev-playlist-bucketer

Sorts a playlist CSV into genre buckets. Each **album** is described to `jev` once, using Last.fm crowd tags (album + artist level) and similar artists; every song on that album inherits the album's buckets.

## Requirements

1. **API keys** in a `.env` file in the project root:
   ```
   TYPESAFE_API_KEY=your-jev-key      # not needed with --dry-run
   LASTFM_API_KEY=your-lastfm-key     # a PAT from last.fm, required
   ```
2. **Buckets** are suggested from your own playlist, in two passes. Pass 1 fetches Last.fm data for every album and writes the dashboard. Pass 2 (real runs only) offers the suggested buckets (tag clusters) in a terminal checklist. Before any jev call it prints how many calls are needed (albums not already cached for the chosen buckets), the bucket count and a few sample inputs, and waits for an explicit yes. Each ticked bucket gets a description built from a fixed template ("Albums tagged X, Y, Z, in the vein of A, B, C.") and is saved to `runs/<timestamp>/selected_buckets.json` (a record of what was scored; editing it has no effect on later runs). Only suggestions are offered; `buckets.json` is no longer read. `other` is built in: it collects albums that clear no bucket's threshold, and jev never sees it.  Every bucket is asked of jev with three generic levels (does not fit / fits somewhat / strongly fits).
3. **Song list CSV** — a [Spotlistr](https://www.spotlistr.com/) export. Rows are `Artist(s) Name , Track Name , Album Name , Release Date , Length , ISRC` (fields separated by ` , `).

## Install

Requires Python 3.10+ and [Poetry](https://python-poetry.org/).

```
poetry install
```

## Usage

```
poetry run python -m bucketer path/to/playlist.csv
```

Run it from the project root: the caches and `runs/` are all resolved relative to the working directory.

With no `--limit` or `--sample` it processes **every row**, and each uncached album is one paid `jev` call. Try `--dry-run` or `--sample` first.

Options:
- `--limit N` — only process the first N rows (default: all rows; ignored with `--sample`)
- `--sample N` / `--seed S` — process N randomly chosen rows, original order kept (default seed 7; the same seed picks the same rows)
- `--threshold X` — minimum score (0-2) for an album to land in a bucket (default 1.0)
- `--dry-run` — skip `jev`; still fetches/caches Last.fm tags and prints the text that would be sent per album, and writes `dashboard.html` (see Output)
- `--yes` — proceed with the jev calls without the confirmation prompt (needed when there is no terminal)
- `--select all|a,b,c` — score with these suggested buckets instead of showing the checklist (needed when there is no terminal)
- `--jev-cache PATH` — `jev` score cache file (default `jev_cache.json`)
- `--no-dashboard` — skip writing the genre dashboard
- `--similar` — also fetch up to 30 similar artists per artist (one extra Last.fm call per uncached artist, cached afterwards) for the dashboard's "Similar to your outliers" section; without it the section uses whatever is already cached
- `--refresh-lastfm` — ignore the Last.fm cache and overwrite it with fresh lookups
- `--refresh-jev` — ignore the `jev` score cache and overwrite it (spends tokens on a real run)

The two `--refresh-*` flags replace the whole cache file, so it afterwards holds only the albums from that run.

Rows that don't have the expected fields are skipped with a warning on stderr.

## How it works

Songs are grouped by (primary artist, cleaned album title); songs with no album are grouped per artist. Each group gets one `jev` request: the state below, plus one score question per bucket.

```
Album: Manic Compression by Quicksand (1995)
Album tags (strongest first): post-hardcore, alternative rock, post-grunge
Artist tags (strongest first): hardcore, emo
Similar artists: Rival Schools, Jawbox, Shiner
```

Tags are cleaned (junk and list tags dropped, nationalities kept, spelling variants merged, generic tags like `rock` ranked last); counts, track titles and ids are never sent.

## Output

`runs/<timestamp>/<bucket>.csv` per bucket (same header and row format as the input; a song can appear in several buckets, and `other.csv` holds songs that matched none), plus `dashboard.html` (unless `--no-dashboard`) (a self-contained Monokai page: up to 30 collapsible suggested-bucket cards from tag clusters, bucket size and coverage, top tags with Last.fm descriptions, tag overlap heatmap, outlier albums that fit no cluster, a searchable all-albums list, Last.fm data-quality tiles, a tag noise audit, release decades per bucket, and (when similar artists are cached) a "Similar to your outliers" table; click a bucket's Browse button or any album row for drill-down), plus `selected_buckets.json` on a real run, plus a summary of Last.fm coverage and `jev` usage.

## Notes

- Wide umbrella tags (rock, pop, alternative, indie, metal, electronic, instrumental, folk, ...) are listed in `UMBRELLA_TAGS` in `bucketer/dashboard/analysis.py`; the dashboard dims them in Top tags and never suggests them as buckets. Edit that set to taste.
- The tag noise audit flags single-album tags and the few uncertain tags (mostly artist names) in `NOISE_TAGS` in `bucketer/dashboard/noise.py`. Definite noise (favourites, ownership, ratings, labels, junk) is dropped earlier by `clean_tags` (`NOISE_TAGS` and patterns in `bucketer/tags.py`), so it never reaches jev or the dashboard; countries and nationalities are kept. Ticked tags can be copied as JSON from the page.
- Album covers on the dashboard come from Last.fm `album.getInfo` (one call per album, stored as `cover` on the `album` cache entry; `""` = Last.fm has none). The page links the Last.fm image URLs, so covers need internet to display; a ♪ placeholder shows when there is none or the image fails to load.
- Tag descriptions on the dashboard come from Last.fm `tag.getInfo` for the top ~40 tags, cached in the `tag` section of `lastfm_cache.json`. `tag.getSimilar` returns nothing in practice, so suggested buckets come from tag co-occurrence in your own playlist.
- Last.fm responses are cached in `lastfm_cache.json` (~4 req/s); `jev` scores in `jev_cache.json`, keyed by the exact state text plus a fingerprint of the bucket questions (keys, descriptions, `not_for`, levels), so editing a bucket re-scores instead of reusing stale scores (old entries stay in the file). Entries from before fingerprints existed are adopted automatically when their bucket keys match the current ones. Delete a file, or use the matching `--refresh-*` flag, to force a refresh.
- Run the tests with `poetry run python -m unittest discover tests`.
