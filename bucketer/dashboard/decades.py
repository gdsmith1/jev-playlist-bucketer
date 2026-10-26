"""Decade distribution of albums, overall and per suggested bucket."""

DOMINANT_SHARE = 0.6  # a bucket is flagged when one decade holds at least this share of its dated albums
MIN_DATED = 5  # ...and it has at least this many dated albums


def decade_stats(records: list[dict], seeds: list[str]) -> dict:
    """Albums counted once, in the bucket they fit best. Albums without a usable release year are counted separately."""
    years = [r["release_year"] for r in records if r["release_year"]]
    if not years:
        return {"decades": [], "overall": {"counts": [], "unknown": len(records)}, "clusters": []}
    decades = list(range(min(years) // 10 * 10, max(years) // 10 * 10 + 1, 10))

    def histogram(rows: list[dict]) -> dict:
        counts = [0] * len(decades)
        for r in rows:
            if r["release_year"]:
                counts[(r["release_year"] - decades[0]) // 10] += 1
        return {"counts": counts, "unknown": sum(1 for r in rows if not r["release_year"])}

    clusters = []
    for seed in seeds:
        hist = histogram([r for r in records if r["best_cluster"] == seed])
        dated = sum(hist["counts"])
        top = max(range(len(decades)), key=lambda i: hist["counts"][i])
        share = hist["counts"][top] / dated if dated else 0.0
        clusters.append({"seed": seed, **hist, "dated": dated, "top_decade": decades[top], "top_share": round(share, 2),
                         "dominated": dated >= MIN_DATED and share >= DOMINANT_SHARE})
    return {"decades": decades, "overall": histogram(records), "clusters": clusters}
