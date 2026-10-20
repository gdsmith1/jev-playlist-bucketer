import argparse
import json
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from .dashboard import write_dashboard
from .formatting import coverage_stats, format_for_jev, format_run_stats
from .jev import FALLBACK_BUCKET, JevClient
from .lastfm import LastfmClient
from .pipeline import assign_to_buckets, group_rows, load_rows, matching_buckets, write_buckets

BUCKETS_PATH = "buckets.json"
JEV_CACHE_PATH = "jev_cache.json"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sort playlist songs into buckets using jev + Last.fm tags, scored once per album.")
    parser.add_argument("csv_path", help="Path to the playlist CSV")
    parser.add_argument("--limit", type=int, help="Only process the first N data rows (default: all; ignored with --sample)")
    parser.add_argument("--sample", type=int, help="Process N randomly chosen rows (original order kept) instead of the first --limit")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for --sample")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum score for an album to be included in a bucket")
    parser.add_argument("--dry-run", action="store_true", help="Skip jev scoring; only fetch metadata and print what would be sent")
    parser.add_argument("--no-dashboard", action="store_true", help="With --dry-run, skip writing the genre dashboard (dashboard.html in the run folder)")
    parser.add_argument("--buckets", default=BUCKETS_PATH, help="Path to the bucket definitions JSON")
    parser.add_argument("--refresh-lastfm", action="store_true", help="Ignore the existing Last.fm cache and overwrite it with fresh lookups")
    parser.add_argument("--refresh-jev", action="store_true", help="Ignore the existing jev score cache and overwrite it (spends jev tokens on a real run)")
    parser.add_argument("--jev-cache", default=JEV_CACHE_PATH, help="Path to the jev score cache JSON")
    return parser.parse_args(argv)


def select_buckets(buckets: dict, groups: list, enrichments: list) -> dict:
    """Selection seam between the dashboard and jev scoring. Pass-through until DASH-11b."""
    return buckets


def main(argv=None) -> None:
    load_dotenv()
    args = parse_args(argv)

    with open(args.buckets) as f:
        buckets = json.load(f)

    lastfm = LastfmClient(refresh=args.refresh_lastfm)
    header, lines = load_rows(args.csv_path, args.limit, args.sample, args.seed)

    run_dir = os.path.join("runs", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    groups = group_rows(lines)
    started = time.monotonic()

    # Pass 1: fetch Last.fm for every album.
    enrichments = []
    for i, group in enumerate(groups, start=1):
        print(f"[{i}/{len(groups)}] {group.artist} - {group.album} ({len(group.rows)} songs)")
        enrichment = lastfm.fetch(group.artist, group.album)
        lastfm.flush()
        enrichments.append(enrichment)
    texts = [format_for_jev(g.artist, g.album, g.release_date, e) for g, e in zip(groups, enrichments)]

    # Analyse and write the dashboard (dry runs only).
    dashboard_path = None
    if args.dry_run and not args.no_dashboard:
        dashboard_path = write_dashboard(run_dir, list(zip(groups, enrichments)), lastfm.tag_info)
        lastfm.flush()

    # Selection hook: DASH-11b picks the buckets to score against here.
    buckets = select_buckets(buckets, groups, enrichments)
    jev = None if args.dry_run else JevClient(buckets, cache_path=args.jev_cache, refresh=args.refresh_jev)

    # Pass 2: score with jev.
    destinations: dict[int, list[str]] = {}  # song index -> bucket keys
    for group, text in zip(groups, texts):
        if args.dry_run:
            print(f"{group.artist} - {group.album}\n  jev input: " + text.replace("\n", "\n             "))
            continue
        matched = matching_buckets(jev.score(text, group.key), args.threshold)
        for index in group.rows:
            destinations[index] = matched

    bucket_lines = assign_to_buckets(lines, destinations, buckets)
    write_buckets(run_dir, header, bucket_lines)

    print()
    print(f"run folder: {run_dir}")
    if dashboard_path:
        print(f"dashboard: {dashboard_path}")
    print(f"songs processed: {len(lines)}  albums scored: {len(groups)}")
    print(format_run_stats(coverage_stats(enrichments), lastfm.stats, time.monotonic() - started))
    for key, matched_lines in bucket_lines.items():
        if matched_lines:
            print(f"  {key}: {len(matched_lines)}")
    if jev:
        print(f"jev calls: {jev.usage['call_count']}")
        print(f"jev input_tokens: {jev.usage['input_tokens']}")
        print(f"jev output_tokens: {jev.usage['output_tokens']}")
