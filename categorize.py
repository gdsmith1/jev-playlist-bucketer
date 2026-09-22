import argparse
import hashlib
import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["TYPESAFE_API_KEY"]
JEV_URL = "https://api.typesafe.ai/v1/systemone"
MB_USER_AGENT = "jev-playlist-bucketer/0.1 ( gibson.smith@liatrio.com )"
MB_MIN_INTERVAL = 1.0  # seconds between MusicBrainz requests

BUCKETS_PATH = "buckets.json"
MB_CACHE_PATH = "mb_cache.json"
JEV_CACHE_PATH = "jev_cache.json"

GENERIC_LEVELS = [
    "Does not fit this bucket at all",
    "Fits this bucket somewhat",
    "Strongly fits this bucket",
]

_last_mb_request_at = 0.0


def load_json_cache(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json_cache(path, cache):
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def mb_throttle():
    global _last_mb_request_at
    elapsed = time.monotonic() - _last_mb_request_at
    if elapsed < MB_MIN_INTERVAL:
        time.sleep(MB_MIN_INTERVAL - elapsed)
    _last_mb_request_at = time.monotonic()


def mb_get(url, params):
    backoff = 1.0
    while True:
        mb_throttle()
        resp = requests.get(
            url, params=params, headers={"User-Agent": MB_USER_AGENT}
        )
        if resp.status_code == 503:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue
        resp.raise_for_status()
        return resp.json()


def dedup_names(*tag_lists):
    seen = set()
    result = []
    for tags in tag_lists:
        for tag in tags or []:
            name = tag["name"]
            if name not in seen:
                seen.add(name)
                result.append(name)
    return result


def fetch_musicbrainz_tags(isrc):
    isrc_data = mb_get(
        f"https://musicbrainz.org/ws/2/isrc/{isrc}",
        {"inc": "tags+artist-credits", "fmt": "json"},
    )
    recordings = isrc_data.get("recordings") or []
    if not recordings:
        return None

    recording_id = recordings[0]["id"]
    recording_data = mb_get(
        f"https://musicbrainz.org/ws/2/recording/{recording_id}",
        {"inc": "genres+tags+artist-credits", "fmt": "json"},
    )

    recording_genres = recording_data.get("genres") or []
    recording_tags = recording_data.get("tags") or []

    artist_genres = []
    artist_tags = []
    for credit in recording_data.get("artist-credit") or []:
        artist = credit.get("artist") or {}
        artist_genres.extend(artist.get("genres") or [])
        artist_tags.extend(artist.get("tags") or [])

    names = dedup_names(recording_genres, artist_genres, recording_tags, artist_tags)
    return names


def get_musicbrainz_tags(isrc, artist, track, mb_cache):
    if isrc in mb_cache:
        return mb_cache[isrc]["tags"]

    try:
        names = fetch_musicbrainz_tags(isrc)
    except requests.RequestException as exc:
        print(f"  MusicBrainz lookup failed for {isrc}: {exc}")
        names = None

    mb_cache[isrc] = {"artist": artist, "track": track, "tags": names}
    save_json_cache(MB_CACHE_PATH, mb_cache)
    return names


def parse_row(line):
    return [field.strip() for field in line.rstrip("\n").split(" , ")]


def build_jev_text(fields, tags):
    artist, track, album, release_date, length, _isrc = fields
    tag_text = ", ".join(tags) if tags else "no tags found"
    return f"{artist}, {track}, {album}, {release_date}, {length}, tags: {tag_text}"


def build_questions(buckets):
    return {
        key: {
            "type": "score",
            "instructions": bucket["description"],
            "criteria": GENERIC_LEVELS,
        }
        for key, bucket in buckets.items()
    }


def score_song(text, artist, track, buckets, jev_cache, usage_totals):
    cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if cache_key in jev_cache:
        return jev_cache[cache_key]["scores"]

    response = requests.post(
        JEV_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "state": text,
            "model": "jev-latest",
            "questions": build_questions(buckets),
        },
    )
    response.raise_for_status()
    data = response.json()

    scores = {key: answer["score"] for key, answer in data["answers"].items()}

    usage = data.get("usage", {})
    usage_totals["input_tokens"] += usage.get("input_tokens", 0)
    usage_totals["output_tokens"] += usage.get("output_tokens", 0)
    usage_totals["call_count"] += 1

    jev_cache[cache_key] = {"artist": artist, "track": track, "scores": scores}
    save_json_cache(JEV_CACHE_PATH, jev_cache)
    return scores


def main():
    parser = argparse.ArgumentParser(description="Sort playlist songs into buckets using jev + MusicBrainz.")
    parser.add_argument("csv_path", help="Path to the playlist CSV (must include an ISRC column)")
    parser.add_argument("--limit", type=int, default=40, help="Max number of data rows to process")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum score for a song to be included in a bucket")
    parser.add_argument("--dry-run", action="store_true", help="Skip jev scoring; only fetch MusicBrainz tags and print what would be sent")
    args = parser.parse_args()

    with open(BUCKETS_PATH) as f:
        buckets = json.load(f)

    mb_cache = load_json_cache(MB_CACHE_PATH)
    jev_cache = load_json_cache(JEV_CACHE_PATH)
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "call_count": 0}

    with open(args.csv_path) as f:
        lines = f.readlines()
    header_line = lines[0].rstrip("\n")
    data_lines = [line for line in lines[1:] if line.strip()][: args.limit]

    run_dir = os.path.join("runs", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    bucket_lines = {key: [] for key in buckets}
    mb_hits = 0
    mb_misses = 0

    for i, line in enumerate(data_lines, start=1):
        fields = parse_row(line)
        isrc = fields[-1]
        artist, track = fields[0], fields[1]
        print(f"[{i}/{len(data_lines)}] {artist} - {track} ({isrc})")

        tags = get_musicbrainz_tags(isrc, artist, track, mb_cache)
        if tags:
            mb_hits += 1
        else:
            mb_misses += 1

        text = build_jev_text(fields, tags)

        if args.dry_run:
            print(f"  jev input: {text}")
            continue

        scores = score_song(text, artist, track, buckets, jev_cache, usage_totals)

        matched_any = False
        for key, score in scores.items():
            if key == "other":
                continue
            if score >= args.threshold:
                bucket_lines[key].append(line.rstrip("\n"))
                matched_any = True

        if not matched_any:
            bucket_lines["other"].append(line.rstrip("\n"))

    for key, matched_lines in bucket_lines.items():
        if not matched_lines:
            continue
        out_path = os.path.join(run_dir, f"{key}.csv")
        with open(out_path, "w") as f:
            f.write(header_line + "\n")
            for matched_line in matched_lines:
                f.write(matched_line + "\n")

    print()
    print(f"run folder: {run_dir}")
    print(f"songs processed: {len(data_lines)}")
    print(f"musicbrainz hits/misses: {mb_hits}/{mb_misses}")
    for key, matched_lines in bucket_lines.items():
        if matched_lines:
            print(f"  {key}: {len(matched_lines)}")
    print(f"jev calls: {usage_totals['call_count']}")
    print(f"jev input_tokens: {usage_totals['input_tokens']}")
    print(f"jev output_tokens: {usage_totals['output_tokens']}")


if __name__ == "__main__":
    main()
