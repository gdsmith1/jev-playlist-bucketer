# jev-playlist-bucketer

Sorts a playlist CSV into genre buckets using MusicBrainz tags + a `jev` scoring API call per song.

## Requirements

1. **API key** — set `TYPESAFE_API_KEY` in a `.env` file in the project root:
   ```
   TYPESAFE_API_KEY=your-key-here
   ```
2. **Bucket definitions** — a `buckets.json` file in the project root defining each genre bucket to score against, e.g.:
   ```json
   {
     "grunge_stoner": {
       "description": "Heavy, sludgy alt-rock in the vein of Kyuss, Soundgarden, Alice in Chains"
     },
     "pop_rock": {
       "description": "Radio-friendly rock with strong melodic hooks"
     },
     "other": {
       "description": "Doesn't fit any other bucket"
     }
   }
   ```
   Include an `other` catch-all — songs that don't clear the threshold for any bucket land there.
3. **Song list CSV** — export a playlist from [Spotlistr](https://www.spotlistr.com/) to CSV. Rows must be `Artist(s) Name , Track Name , Album Name , Release Date , Length , ISRC` (fields separated by ` , `, ISRC as the last column — required for MusicBrainz lookups).

## Install

```
poetry install
```

## Usage

```
poetry run python categorize.py path/to/playlist.csv
```

Options:
- `--limit N` — max number of rows to process (default 40)
- `--threshold X` — minimum score (0–2) for a song to be included in a bucket (default 1.0)
- `--dry-run` — skip the `jev` API call entirely; still fetches/caches MusicBrainz tags and prints the text that would be sent for scoring (no buckets are written)

## Output

Each run writes bucketed CSVs to `runs/<timestamp>/<bucket>.csv`, plus a summary of MusicBrainz hit/miss counts and `jev` API usage (call count, tokens).

## Notes

- MusicBrainz lookups are cached in `mb_cache.json` and throttled to ~1 request/sec.
- `jev` scoring results are cached in `jev_cache.json`, keyed by the exact input text, so re-runs skip already-scored songs.
- Both cache files are safe to delete to force a full re-fetch/re-score.
