"""Synthetic playlist for `--demo`: builds the dashboard with no CSV, Last.fm or jev, so UI work iterates in about a second."""

import random

from .checkpoint import suggest_buckets
from .dashboard import analyze, song_dicts, write_dashboard
from .models import Enrichment
from .pipeline import group_rows

# genre -> (tags that co-occur, artist name stems). Co-occurring tags make the clusters, heatmap and bucket cards look real.
GENRES = {
    "stoner rock": (["stoner rock", "desert rock", "heavy metal", "doom metal", "rock"], ["Kyuss", "Sleep", "Electric Wizard", "Fu Manchu", "Monster Magnet", "Truckfighters"]),
    "indie pop": (["indie pop", "dream pop", "indie", "alternative", "pop"], ["Beach House", "Clairo", "Alvvays", "Wet", "Men I Trust", "Japanese Breakfast"]),
    "hip hop": (["hip-hop", "rap", "boom bap", "underground hip-hop", "alternative hip-hop"], ["MF DOOM", "Madlib", "Black Star", "Jeru", "Blu", "Mos Def"]),
    "electronic": (["electronic", "ambient", "idm", "downtempo", "experimental"], ["Boards of Canada", "Aphex Twin", "Bonobo", "Tycho", "Four Tet", "Floating Points"]),
    "jazz": (["jazz", "modal jazz", "hard bop", "bebop", "instrumental"], ["Miles Davis", "John Coltrane", "Art Blakey", "Bill Evans", "Herbie Hancock", "Sonny Rollins"]),
    "folk": (["folk", "singer-songwriter", "indie folk", "acoustic", "americana"], ["Fleet Foxes", "Bon Iver", "Iron and Wine", "Nick Drake", "Joni Mitchell", "Big Thief"]),
    "metal": (["metal", "thrash metal", "heavy metal", "death metal", "hard rock"], ["Metallica", "Slayer", "Mastodon", "Gojira", "Opeth", "Baroness"]),
    "soul": (["soul", "rnb", "neo-soul", "funk", "groove"], ["D'Angelo", "Erykah Badu", "Sade", "Curtis Mayfield", "Anderson .Paak", "SZA"]),
}
OTHER_TAGS = ["seen live", "favorites", "00s", "90s", "70s", "usa", "british", "female vocalists"]
WORDS = ["Echo", "Static", "Garden", "Signal", "Harbor", "Velvet", "Orbit", "Paper", "Ember", "Tide", "Neon", "Hollow", "Bloom", "Drift", "Atlas", "Lantern"]
TITLES = ["Opening", "Interlude", "Night Drive", "Slow Burn", "Afterglow", "Departure", "Blue Hour", "Wildfire", "Homecoming", "Fade", "Reprise", "Undertow"]
SELECTED = 5  # how many suggested buckets the demo "scores"


def demo_playlist(albums: int, seed: int):
    """(lines, groups, enrichments, tag_info) for a seeded fake playlist with a few unknown and untagged albums."""
    rng = random.Random(seed)
    lines, enrichments = [], []
    for n in range(albums):
        genre = rng.choices(list(GENRES), weights=[5, 4, 4, 3, 3, 3, 2, 2])[0] if n % 11 else None
        tags, artists = GENRES[genre] if genre else (OTHER_TAGS, [rng.choice(WORDS) + " Collective"])
        artist = rng.choice(artists)
        album = f"{rng.choice(WORDS)} {rng.choice(WORDS)} {n}"
        year = rng.randint(1968, 2024)
        picked = rng.sample(tags, k=min(len(tags), rng.randint(2, 4))) + rng.sample(OTHER_TAGS, k=int(rng.random() < 0.12))
        for song in range(rng.randint(1, 7)):
            lines.append(f"{artist} , {rng.choice(TITLES)} {song + 1} , {album} , {year} , 3:30 , DEMO{n:03}{song}")
        counts = sorted((rng.randint(20, 100) for _ in picked), reverse=True)
        tag_list = [{"name": t, "count": c} for t, c in zip(picked, counts)]
        enrichments.append(Enrichment(album_tags=tag_list, artist_tags=tag_list[:2], similar_artists=rng.sample(artists, k=min(3, len(artists))),
                                      similar_full=[{"name": a, "match": round(rng.random(), 2)} for a in artists[:5]]))
    groups = group_rows(lines)
    tag_info = {t: {"summary": f"Demo description for the {t} tag.", "reach": 1000 + 37 * len(t)} for tags, _ in GENRES.values() for t in tags}
    return lines, groups, enrichments, tag_info


def demo_scores(suggested: dict, groups, enrichments, rng: random.Random) -> list[dict]:
    """Fake jev results: an album scores high on a bucket when its tags overlap the bucket's tags, plus noise."""
    result = []
    for e in enrichments:
        names = {t["name"] for t in (e.album_tags or [])}
        scores = {key: round(min(1.0, max(0.0, (0.95 if names & set(b["tags"]) else 0.3) + rng.uniform(-0.3, 0.12))), 2) for key, b in suggested.items()}
        result.append({"scores": scores, "matched": [k for k, s in scores.items() if s >= 0.8]})
    return result


def build_demo(run_dir: str, albums: int = 90, seed: int = 7, threshold: float = 0.8) -> str:
    """Write runs/<ts>/dashboard.html from synthetic data, with the Selected buckets tab filled in. Returns the path."""
    lines, groups, enrichments, tag_info = demo_playlist(albums, seed)
    pairs = list(zip(groups, enrichments))
    suggested = suggest_buckets(analyze(pairs)["clusters"])
    chosen = {k: {"description": b["description"], "source": "recommended"} for k, b in list(suggested.items())[:SELECTED]}
    albums_scored = demo_scores({k: suggested[k] for k in chosen}, groups, enrichments, random.Random(seed))
    jev_result = {"threshold": threshold, "buckets": chosen, "albums": albums_scored}
    return write_dashboard(run_dir, pairs, lambda t: tag_info.get(t), jev_result=jev_result, songs=song_dicts(lines, groups))
