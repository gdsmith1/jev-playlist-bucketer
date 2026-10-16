# jev-playlist-bucketer

Sorts a playlist CSV into genre buckets. Each **album** is described to `jev` once, using Last.fm crowd tags (album + artist level) and similar artists; every song on that album inherits the album's buckets.

## Requirements

1. **API keys** in a `.env` file in the project root:
   ```
   TYPESAFE_API_KEY=your-jev-key      # not needed with --dry-run
   LASTFM_API_KEY=your-lastfm-key     # a PAT from last.fm, required
   ```
2. **Bucket definitions** — a `buckets.json` in the project root:
   ```json
   {
     "grunge_stoner": {
       "description": "Heavy, sludgy alt-rock in the vein of Kyuss, Soundgarden, Alice in Chains",
       "not_for": "polished radio rock",
       "levels": [
         "Not grunge or stoner rock",
         {"summary": "Some grunge or stoner influence", "signals": ["alternative rock with heavy riffs"]},
         {"summary": "Clearly grunge or stoner rock", "signals": ["stoner rock", "desert rock", "grunge"]}
       ]
     }
   }
   ```
   `description` is required. `levels` (2-10 strings or `{summary, signals}` objects) and `not_for` are optional; without `levels` three generic levels are used. `other` is built in: it collects albums that clear no bucket's threshold. jev never sees it, and you don't need to define it (an entry named `other` is ignored).
3. **Song list CSV** — a [Spotlistr](https://www.spotlistr.com/) export. Rows are `Artist(s) Name , Track Name , Album Name , Release Date , Length , ISRC` (fields separated by ` , `).

## Install

```
poetry install
```

## Usage

```
poetry run python -m bucketer path/to/playlist.csv
```

Options:
- `--limit N` — max rows to process (default 40, ignored with `--sample`)
- `--sample N` / `--seed S` — process N randomly chosen rows (default seed 7)
- `--threshold X` — minimum score (0-2) for an album to land in a bucket (default 1.0)
- `--dry-run` — skip `jev`; still fetches/caches Last.fm tags and prints the text that would be sent per album

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

`runs/<timestamp>/<bucket>.csv` per bucket, plus a summary of Last.fm coverage and `jev` usage.

## Notes

- Last.fm responses are cached in `lastfm_cache.json` (~4 req/s); `jev` scores in `jev_cache.json`, keyed by the exact state text. Delete either to force a refresh.
- Run the tests with `poetry run python -m unittest discover tests`.
