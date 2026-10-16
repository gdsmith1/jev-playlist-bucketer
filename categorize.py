import argparse
import hashlib
import json
import os
import random
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from enrichment import clean_album, coverage_stats, format_for_jev, format_run_stats, is_unknown_album, primary_artist
from providers.lastfm import Provider

load_dotenv()

JEV_URL = "https://api.typesafe.ai/v1/systemone"

BUCKETS_PATH = "buckets.json"
JEV_CACHE_PATH = "jev_cache.json"

# Albums that clear no bucket's threshold land here. jev never sees it: it is not a question,
# and any bucket with this name in buckets.json is ignored.
FALLBACK_BUCKET = "other"

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
    """One score question per bucket ("other" is the fallback, not a judgment).
    A bucket may define `levels` (2-10 strings or {summary, signals}) and `not_for`
    (lookalikes that do not belong); otherwise generic levels are used."""
    questions = {}
    for key, bucket in buckets.items():
        if key == FALLBACK_BUCKET:
            continue
        instructions = f"Does the album described in `state` fit this genre bucket? {bucket['description']}"
        if bucket.get("not_for"):
            instructions += f" Not for: {bucket['not_for']}"
        questions[key] = {
            "type": "score",
            "instructions": instructions,
            "criteria": bucket.get("levels") or GENERIC_LEVELS,
        }
    return questions


def group_key(artist, album):
    """Songs share a jev decision per (primary artist, cleaned album). Songs with no
    album are grouped per artist, since only artist tags are available for them."""
    a = primary_artist(artist).lower()
    return f"{a}|" if is_unknown_album(album) else f"{a}|{clean_album(album).lower()}"


def score_group(text, label, buckets, jev_cache, usage_totals):
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
    confidence = {key: answer.get("confidence") for key, answer in data["answers"].items()}

    usage = data.get("usage", {})
    usage_totals["input_tokens"] += usage.get("input_tokens", 0)
    usage_totals["output_tokens"] += usage.get("output_tokens", 0)
    usage_totals["call_count"] += 1

    jev_cache[cache_key] = {"label": label, "scores": scores, "confidence": confidence}
    save_json_cache(JEV_CACHE_PATH, jev_cache)
    return scores


def main():
    parser = argparse.ArgumentParser(description="Sort playlist songs into buckets using jev + Last.fm tags, scored once per album.")
    parser.add_argument("csv_path", help="Path to the playlist CSV")
    parser.add_argument("--limit", type=int, default=40, help="Max number of data rows to process (ignored with --sample)")
    parser.add_argument("--sample", type=int, help="Process N randomly chosen rows (original order kept) instead of the first --limit")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for --sample")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum score for an album to be included in a bucket")
    parser.add_argument("--dry-run", action="store_true", help="Skip jev scoring; only fetch metadata and print what would be sent")
    args = parser.parse_args()

    with open(BUCKETS_PATH) as f:
        buckets = json.load(f)

    provider = Provider()
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

    groups = {}  # insertion-ordered: group key -> {"fields": first row's fields, "lines": [...]}
    for line in data_lines:
        fields = parse_row(line)
        key = group_key(fields[0], fields[2])
        groups.setdefault(key, {"fields": fields, "lines": []})["lines"].append(line.rstrip("\n"))

    destinations = {}  # song line -> bucket keys
    enrichments = []
    started = time.monotonic()

    for i, (key, group) in enumerate(groups.items(), start=1):
        artist, album, release_date = group["fields"][0], group["fields"][2], group["fields"][3]
        print(f"[{i}/{len(groups)}] {artist} - {album} ({len(group['lines'])} songs)")

        enrichment = provider.fetch(artist, album)
        provider.flush()
        enrichments.append(enrichment)

        text = format_for_jev(artist, album, release_date, enrichment)

        if args.dry_run:
            print("  jev input: " + text.replace("\n", "\n             "))
            continue

        scores = score_group(text, key, buckets, jev_cache, usage_totals)
        matched = [k for k, score in scores.items() if k != FALLBACK_BUCKET and score >= args.threshold]
        for line in group["lines"]:
            destinations[line] = matched or [FALLBACK_BUCKET]

    bucket_lines = {key: [] for key in buckets if key != FALLBACK_BUCKET}
    bucket_lines[FALLBACK_BUCKET] = []
    for line in data_lines:
        line = line.rstrip("\n")
        for key in destinations.get(line, []):
            bucket_lines[key].append(line)

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
    print(f"songs processed: {len(data_lines)}  albums scored: {len(groups)}")
    print(format_run_stats("lastfm", coverage_stats(enrichments), provider.stats, time.monotonic() - started))
    for key, matched_lines in bucket_lines.items():
        if matched_lines:
            print(f"  {key}: {len(matched_lines)}")
    print(f"jev calls: {usage_totals['call_count']}")
    print(f"jev input_tokens: {usage_totals['input_tokens']}")
    print(f"jev output_tokens: {usage_totals['output_tokens']}")


if __name__ == "__main__":
    main()
