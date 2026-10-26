"""Pure summary of the buckets the user created and jev scored: sizes, other, overlap, agreement with tag fit, borderline albums."""

BORDERLINE_BELOW = 0.25  # a score this close under the threshold counts as borderline
TOP_ALBUMS = 8
MAX_BORDERLINE = 200


def jev_record(entry: dict) -> dict:
    """Compact per-album jev data embedded in an album record."""
    return {"scores": {k: round(v, 2) for k, v in entry["scores"].items()}, "matched": list(entry["matched"])}


def summarize(records: list[dict], jev_result: dict, cluster_seeds: list[str]) -> dict:
    """Records carry `songs`, `artist`, `album`, `buckets` (tag-fit assignment) and `jev` (scores, matched)."""
    threshold = jev_result["threshold"]
    keys = list(jev_result["buckets"])
    seeds = set(cluster_seeds)
    songs = lambda rs: sum(r["songs"] for r in rs)
    matched = lambda r: [k for k in r["jev"]["matched"] if k in jev_result["buckets"]]
    other = [r for r in records if not matched(r)]
    several = [r for r in records if len(matched(r)) > 1]
    buckets = []
    for key in keys:
        meta = jev_result["buckets"][key]
        mine = [r for r in records if key in matched(r)]
        top = sorted(mine, key=lambda r: (-r["jev"]["scores"].get(key, 0), -r["songs"]))[:TOP_ALBUMS]
        row = {"key": key, "description": meta.get("description", ""), "source": meta.get("source", "custom"), "albums": len(mine), "songs": songs(mine),
               "shared": sum(len(matched(r)) > 1 for r in mine),
               "top": [{"artist": r["artist"], "album": r["album"], "songs": r["songs"], "score": r["jev"]["scores"].get(key, 0)} for r in top]}
        if row["source"] == "recommended" and key in seeds:
            by_tags = [r for r in records if key in r["buckets"]]
            both = sum(key in matched(r) for r in by_tags)
            row["agreement"] = {"jev": len(mine), "tags": len(by_tags), "both": both, "jev_only": len(mine) - both, "tags_only": len(by_tags) - both}
        buckets.append(row)
    near = [{"artist": r["artist"], "album": r["album"], "bucket": k, "score": s} for r in records
            for k, s in r["jev"]["scores"].items() if k in jev_result["buckets"] and threshold - BORDERLINE_BELOW <= s < threshold]
    near.sort(key=lambda b: -b["score"])
    return {"threshold": threshold, "bucket_count": len(keys), "buckets": buckets,
            "other": {"albums": len(other), "songs": songs(other)}, "several": {"albums": len(several), "songs": songs(several)},
            "one": {"albums": len(records) - len(other) - len(several), "songs": songs(records) - songs(other) - songs(several)},
            "borderline": {"total": len(near), "rows": near[:MAX_BORDERLINE]}, "borderline_below": BORDERLINE_BELOW}
