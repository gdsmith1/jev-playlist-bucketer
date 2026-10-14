import argparse
import hashlib
import json
import os
import random
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from enrichment import coverage_stats, format_for_jev, format_run_stats
from providers import PROVIDER_NAMES, get_provider

load_dotenv()

JEV_URL = "https://api.typesafe.ai/v1/systemone"

BUCKETS_PATH = "buckets.json"
JEV_CACHE_PATH = "jev_cache.json"

GENERIC_LEVELS = [
    "Does not fit this bucket at all",
    "Fits this bucket somewhat",
    "Strongly fits this bucket",
]

def load_json_cache(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json_cache(path, cache):
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def parse_row(line):
    return [field.strip() for field in line.rstrip("\n").split(" , ")]


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

    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise SystemExit("TYPESAFE_API_KEY is not set (needed to score with jev; not needed with --dry-run)")

    response = requests.post(
        JEV_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
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
    parser = argparse.ArgumentParser(description="Sort playlist songs into buckets using jev + enriched song metadata.")
    parser.add_argument("csv_path", help="Path to the playlist CSV (must include an ISRC column)")
    parser.add_argument("--limit", type=int, default=40, help="Max number of data rows to process (ignored with --sample)")
    parser.add_argument("--source", choices=PROVIDER_NAMES, default="musicbrainz", help="Metadata provider")
    parser.add_argument("--sample", type=int, help="Process N randomly chosen rows (original order kept) instead of the first --limit")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for --sample")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum score for a song to be included in a bucket")
    parser.add_argument("--dry-run", action="store_true", help="Skip jev scoring; only fetch metadata and print what would be sent")
    args = parser.parse_args()

    with open(BUCKETS_PATH) as f:
        buckets = json.load(f)

    provider = get_provider(args.source)
    jev_cache = load_json_cache(JEV_CACHE_PATH)
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "call_count": 0}

    with open(args.csv_path) as f:
        lines = f.readlines()
    header_line = lines[0].rstrip("\n")
    data_lines = [line for line in lines[1:] if line.strip()]
    if args.sample is not None:
        picked = sorted(random.Random(args.seed).sample(range(len(data_lines)), min(args.sample, len(data_lines))))
        data_lines = [data_lines[i] for i in picked]
    else:
        data_lines = data_lines[: args.limit]

    run_dir = os.path.join("runs", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    bucket_lines = {key: [] for key in buckets}
    enrichments = []
    started = time.monotonic()

    for i, line in enumerate(data_lines, start=1):
        fields = parse_row(line)
        isrc = fields[-1]
        artist, track, album = fields[0], fields[1], fields[2]
        print(f"[{i}/{len(data_lines)}] {artist} - {track} ({isrc})")

        enrichment = provider.fetch(artist, track, album, isrc)
        provider.flush()
        enrichments.append(enrichment)

        text = format_for_jev(fields, enrichment)

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
    print(format_run_stats(args.source, coverage_stats(enrichments), provider.stats, time.monotonic() - started))
    for key, matched_lines in bucket_lines.items():
        if matched_lines:
            print(f"  {key}: {len(matched_lines)}")
    print(f"jev calls: {usage_totals['call_count']}")
    print(f"jev input_tokens: {usage_totals['input_tokens']}")
    print(f"jev output_tokens: {usage_totals['output_tokens']}")


if __name__ == "__main__":
    main()
