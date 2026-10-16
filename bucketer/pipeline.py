"""Playlist CSV in, bucketed CSVs out: row parsing, sampling, grouping by album, writing buckets."""

import os
import random
import sys

from .jev import FALLBACK_BUCKET
from .models import Group
from .names import clean_album, is_unknown_album, primary_artist

MIN_FIELDS = 4  # artist, track, album, release date


def parse_row(line: str) -> list[str]:
    return [field.strip() for field in line.rstrip("\n").split(" , ")]


def group_key(artist: str, album: str) -> str:
    """Songs share a jev decision per (primary artist, cleaned album). Songs with no
    album are grouped per artist, since only artist tags are available for them."""
    a = primary_artist(artist).lower()
    return f"{a}|" if is_unknown_album(album) else f"{a}|{clean_album(album).lower()}"


def load_rows(csv_path: str, limit: int, sample: int | None = None, seed: int = 7) -> tuple[str, list[str]]:
    """Return (header line, song lines). `sample` picks N rows at random (original order kept)
    instead of the first `limit`. Rows too short to hold an album are skipped with a warning."""
    with open(csv_path) as f:
        lines = f.readlines()
    header = lines[0].rstrip("\n")
    data_lines = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if len(parse_row(line)) < MIN_FIELDS:
            print(f"warning: skipping malformed row {number}: {line.rstrip()!r}", file=sys.stderr)
            continue
        data_lines.append(line.rstrip("\n"))
    if sample is not None:
        picked = sorted(random.Random(seed).sample(range(len(data_lines)), min(sample, len(data_lines))))
        return header, [data_lines[i] for i in picked]
    return header, data_lines[:limit]


def group_rows(lines: list[str]) -> list[Group]:
    """Group song lines by album, in first-seen order. Each group keeps the first row's fields."""
    groups: dict[str, Group] = {}
    for index, line in enumerate(lines):
        fields = parse_row(line)
        key = group_key(fields[0], fields[2])
        if key not in groups:
            groups[key] = Group(key=key, artist=fields[0], album=fields[2], release_date=fields[3])
        groups[key].rows.append(index)
    return list(groups.values())


def matching_buckets(scores: dict[str, float], threshold: float) -> list[str]:
    matched = [k for k, score in scores.items() if k != FALLBACK_BUCKET and score >= threshold]
    return matched or [FALLBACK_BUCKET]


def assign_to_buckets(lines: list[str], destinations: dict[int, list[str]], bucket_keys) -> dict[str, list[str]]:
    """bucket -> song lines, in playlist order. Rows with no destination (dry run) land nowhere."""
    bucket_lines = {key: [] for key in bucket_keys if key != FALLBACK_BUCKET}
    bucket_lines[FALLBACK_BUCKET] = []
    for index, line in enumerate(lines):
        for key in destinations.get(index, []):
            bucket_lines[key].append(line)
    return bucket_lines


def write_buckets(run_dir: str, header: str, bucket_lines: dict[str, list[str]]) -> None:
    for key, matched_lines in bucket_lines.items():
        if not matched_lines:
            continue
        with open(os.path.join(run_dir, f"{key}.csv"), "w") as f:
            f.write(header + "\n")
            for line in matched_lines:
                f.write(line + "\n")
