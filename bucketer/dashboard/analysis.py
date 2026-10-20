"""Pure analysis for the genre dashboard: tag clusters, outliers and one record per album. No jev involved."""

import re

from ..models import Enrichment, Group
from .quality import quality_stats

# Wide umbrella tags: shown in Top tags (dimmed) but never suggested as buckets, never used for clustering or outlier fit. Edit freely.
UMBRELLA_TAGS = frozenset({"rock", "pop", "alternative", "alternative rock", "indie", "metal", "electronic", "instrumental", "folk"})
HEAT_TAGS = 24  # tags in the overlap matrix
TOP_TAGS = 40  # tags considered for clusters, heatmap and descriptions
MIN_WEIGHT = 0.15  # a tag only counts for an album above this share of its top tag
JOIN_SIMILARITY = 0.25  # Jaccard needed for a tag to join an existing cluster instead of seeding its own
MAX_CLUSTERS = 12
OUTLIER_FIT = 0.3  # an album is an outlier when less than this share of its tag weight lands in its best cluster
EXAMPLES_PER_CLUSTER = 6
COVERS_PER_CLUSTER = 5
UNCOUNTED_WEIGHT = 0.5  # weight for a tag that came without a count


def _weighted_tags(enrichment: Enrichment) -> dict[str, tuple[float, str]]:
    """Tag name -> (weight 0-1, source), best of album-level and artist-level, weak tags dropped."""
    found: dict[str, tuple[float, str]] = {}
    for source, tags in (("album", enrichment.album_tags), ("artist", enrichment.artist_tags)):
        for tag in tags or []:
            w = min((tag.get("count") or 0) / 100 or UNCOUNTED_WEIGHT, 1.0)
            if tag["name"] not in found or w > found[tag["name"]][0]:
                found[tag["name"]] = (w, source)
    return {name: pair for name, pair in found.items() if pair[0] >= MIN_WEIGHT}


def album_tags(enrichment: Enrichment) -> dict[str, float]:
    """Tag name -> weight (0-1) for one album, best of album-level and artist-level, weak tags dropped."""
    return {name: w for name, (w, _) in _weighted_tags(enrichment).items()}


def release_year(release_date: str) -> int | None:
    """First plausible four-digit year in a release date, or None for blank, malformed or placeholder dates."""
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", release_date or "")
    return int(match.group(1)) if match and 1900 <= int(match.group(1)) <= 2100 else None


def _jaccard(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def analyze(pairs: list[tuple[Group, Enrichment]]) -> dict:
    albums = []
    for group, enrichment in pairs:
        weighted = _weighted_tags(enrichment)
        albums.append({"artist": group.artist, "album": group.album, "songs": len(group.rows), "tags": {n: w for n, (w, _) in weighted.items()},
                       "sources": {n: s for n, (_, s) in weighted.items()}, "similar": list(enrichment.similar_artists), "cover": enrichment.cover or "",
                       "year": release_year(group.release_date), "has_album_tags": bool(enrichment.album_tags),
                       "has_artist_tags": bool(enrichment.artist_tags)})

    members: dict[str, set[int]] = {}  # tag -> indexes of albums carrying it
    for i, a in enumerate(albums):
        for tag in a["tags"]:
            members.setdefault(tag, set()).add(i)
    songs_of = lambda idx: sum(albums[i]["songs"] for i in idx)  # noqa: E731
    ranked = sorted(members, key=lambda t: (-songs_of(members[t]), -len(members[t]), t))
    top = [t for t in ranked if t not in UMBRELLA_TAGS][:TOP_TAGS]  # bucket candidates
    keep = set(top) | set(ranked[:TOP_TAGS])
    shown = [t for t in ranked if t in keep]  # Top tags chart also keeps umbrella tags

    tag_stats = [{"tag": t, "albums": len(members[t]), "songs": songs_of(members[t]), "umbrella": t in UMBRELLA_TAGS} for t in shown]
    heat_tags = top[:HEAT_TAGS]
    heat = [[round(_jaccard(members[x], members[y]), 3) for y in heat_tags] for x in heat_tags]

    # Greedy clustering: walk tags by popularity; join the most similar existing seed or become a new one.
    clusters: list[dict] = []
    for tag in top:
        best, best_sim = None, 0.0
        for c in clusters:
            sim = _jaccard(members[tag], members[c["seed"]])
            if sim > best_sim:
                best, best_sim = c, sim
        if best is not None and best_sim >= JOIN_SIMILARITY:
            best["tags"].append(tag)
        elif len(clusters) < MAX_CLUSTERS:
            clusters.append({"seed": tag, "tags": [tag]})
        elif best is not None:
            best["tags"].append(tag)

    for c in clusters:
        tagset = set(c["tags"])
        affinity = {i: sum(w for t, w in a["tags"].items() if t in tagset) for i, a in enumerate(albums)}
        mine = {i for i, v in affinity.items() if v > 0}
        c["albums"], c["songs"] = len(mine), songs_of(mine)
        c["examples"] = [f"{albums[i]['artist']}" for i in sorted(mine, key=lambda i: -affinity[i])][:EXAMPLES_PER_CLUSTER]
        c["examples"] = list(dict.fromkeys(c["examples"]))
        ordered = sorted(mine, key=lambda i: (-affinity[i], -albums[i]["songs"]))
        c["covers"] = [{"url": albums[i]["cover"], "title": f"{albums[i]['artist']} - {albums[i]['album']}"} for i in ordered if albums[i]["cover"]][:COVERS_PER_CLUSTER]
    clusters.sort(key=lambda c: -c["songs"])

    outliers = []
    records = []
    for a in albums:
        specific = {t: w for t, w in a["tags"].items() if t not in UMBRELLA_TAGS}
        total = sum(specific.values())
        fits = [(sum(w for t, w in specific.items() if t in c["tags"]) / total if total else 0.0, c["seed"]) for c in clusters]
        fit, nearest = max(fits, default=(0.0, None))
        ranked_fits = sorted(fits, key=lambda f: -f[0])
        records.append({"artist": a["artist"], "album": a["album"], "songs": a["songs"], "cover": a["cover"], "release_year": a["year"],
                        "tags": [{"name": t, "weight": round(w, 3), "source": a["sources"][t]} for t, w in sorted(a["tags"].items(), key=lambda kv: -kv[1])],
                        "similar": a["similar"], "cluster_fits": {seed: round(share, 3) for share, seed in fits},
                        "best_cluster": ranked_fits[0][1] if ranked_fits and ranked_fits[0][0] > 0 else None,
                        "second_best_cluster": ranked_fits[1][1] if len(ranked_fits) > 1 and ranked_fits[1][0] > 0 else None,
                        "has_album_tags": a["has_album_tags"], "has_artist_tags": a["has_artist_tags"]})
        if total == 0 or fit < OUTLIER_FIT:
            outliers.append({"artist": a["artist"], "album": a["album"], "songs": a["songs"], "reason": ("untagged" if not a["tags"] else "only umbrella tags") if total == 0 else "no cluster fits",
                             "cover": a["cover"], "fit": round(fit, 2), "nearest": nearest if fit > 0 else None,
                             "tags": sorted(specific or a["tags"], key=lambda t: -a["tags"][t])[:6], "similar": a["similar"]})
    outliers.sort(key=lambda o: (o["fit"], -o["songs"]))

    total_songs = sum(a["songs"] for a in albums)
    return {"albums": len(albums), "songs": total_songs, "tags": tag_stats, "heat_tags": heat_tags, "heat": heat, "clusters": clusters, "outliers": outliers,
            "outlier_songs": sum(o["songs"] for o in outliers), "album_records": records,
            "quality": quality_stats(records)}
