import argparse
import json
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from .formatting import coverage_stats, format_for_jev, format_run_stats
from .jev import FALLBACK_BUCKET, JevClient
from .lastfm import LastfmClient
from .pipeline import assign_to_buckets, group_rows, load_rows, matching_buckets, write_buckets

BUCKETS_PATH = "buckets.json"
JEV_CACHE_PATH = "jev_cache.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sort playlist songs into buckets using jev + Last.fm tags, scored once per album.")
    parser.add_argument("csv_path", help="Path to the playlist CSV")
    parser.add_argument("--limit", type=int, default=40, help="Max number of data rows to process (ignored with --sample)")
    parser.add_argument("--sample", type=int, help="Process N randomly chosen rows (original order kept) instead of the first --limit")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for --sample")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum score for an album to be included in a bucket")
    parser.add_argument("--dry-run", action="store_true", help="Skip jev scoring; only fetch metadata and print what would be sent")
    parser.add_argument("--buckets", default=BUCKETS_PATH, help="Path to the bucket definitions JSON")
    parser.add_argument("--refresh-lastfm", action="store_true", help="Ignore the existing Last.fm cache and overwrite it with fresh lookups")
    parser.add_argument("--refresh-jev", action="store_true", help="Ignore the existing jev score cache and overwrite it (spends jev tokens on a real run)")
    parser.add_argument("--jev-cache", default=JEV_CACHE_PATH, help="Path to the jev score cache JSON")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    load_dotenv()
    args = parse_args(argv)

    with open(args.buckets) as f:
        buckets = json.load(f)

    lastfm = LastfmClient(refresh=args.refresh_lastfm)
    jev = JevClient(buckets, cache_path=args.jev_cache, refresh=args.refresh_jev)

    header, lines = load_rows(args.csv_path, args.limit, args.sample, args.seed)

    run_dir = os.path.join("runs", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    groups = group_rows(lines)
    destinations: dict[int, list[str]] = {}  # song index -> bucket keys
    enrichments = []
    started = time.monotonic()

    for i, group in enumerate(groups, start=1):
        print(f"[{i}/{len(groups)}] {group.artist} - {group.album} ({len(group.rows)} songs)")

        enrichment = lastfm.fetch(group.artist, group.album)
        lastfm.flush()
        enrichments.append(enrichment)

        text = format_for_jev(group.artist, group.album, group.release_date, enrichment)

        if args.dry_run:
            print("  jev input: " + text.replace("\n", "\n             "))
            continue

        matched = matching_buckets(jev.score(text, group.key), args.threshold)
        for index in group.rows:
            destinations[index] = matched

    bucket_lines = assign_to_buckets(lines, destinations, buckets)
    write_buckets(run_dir, header, bucket_lines)

    print()
    print(f"run folder: {run_dir}")
    print(f"songs processed: {len(lines)}  albums scored: {len(groups)}")
    print(format_run_stats(coverage_stats(enrichments), lastfm.stats, time.monotonic() - started))
    for key, matched_lines in bucket_lines.items():
        if matched_lines:
            print(f"  {key}: {len(matched_lines)}")
    print(f"jev calls: {jev.usage['call_count']}")
    print(f"jev input_tokens: {jev.usage['input_tokens']}")
    print(f"jev output_tokens: {jev.usage['output_tokens']}")
