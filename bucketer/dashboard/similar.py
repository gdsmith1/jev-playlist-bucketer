"""Last.fm similar-artist neighbours of the outlier artists: who in the playlist they resemble, and who is missing from it."""

from collections import Counter

from ..names import primary_artist

MIN_MATCH = 0.2  # ignore weakly similar artists
ROWS = 30
OUTSIDERS_PER_ROW = 4
RECOMMENDED = 15


def _key(artist: str) -> str:
    return primary_artist(artist).strip().lower()


def similar_to_outliers(albums: list[dict], records: list[dict], outliers: list[dict]) -> dict:
    """`albums` carry `artist` and `similar_full` ([{name, match}]); `records` carry `best_cluster`. Rows follow the outlier table order."""
    playlist = {_key(a["artist"]) for a in albums}
    outlier_artists = {_key(o["artist"]) for o in outliers}
    bucket_of: dict[str, Counter] = {}
    for r in records:
        k = _key(r["artist"])
        if r["best_cluster"] and k not in outlier_artists:
            bucket_of.setdefault(k, Counter())[r["best_cluster"]] += r["songs"]
    similar = {}
    for a in albums:
        if a["similar_full"]:
            similar.setdefault(_key(a["artist"]), a["similar_full"])

    rows, recommended = [], Counter()
    for o in outliers:
        own = _key(o["artist"])
        neighbours = [s for s in similar.get(own, []) if s["match"] >= MIN_MATCH and _key(s["name"]) != own]
        inside = [s for s in neighbours if _key(s["name"]) in playlist]
        outside = [s for s in neighbours if _key(s["name"]) not in playlist]
        for s in outside:
            recommended[s["name"]] += s["match"]
        leaning: Counter = Counter()
        for s in inside:
            counts = bucket_of.get(_key(s["name"]))
            if counts:
                total = sum(counts.values())
                for seed, songs in counts.items():
                    leaning[seed] += s["match"] * songs / total
        if neighbours:
            rows.append({"artist": o["artist"], "inside": [s["name"] for s in inside][:6], "outside": [s["name"] for s in outside][:OUTSIDERS_PER_ROW],
                         "leans": leaning.most_common(1)[0][0] if leaning else None})
    return {"rows": rows[:ROWS], "with_neighbours": len(rows), "outliers": len(outliers),
            "recommended": [{"artist": n, "score": round(s, 2)} for n, s in recommended.most_common(RECOMMENDED)]}
