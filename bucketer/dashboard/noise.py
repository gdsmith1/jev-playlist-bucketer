"""Tag noise audit: tags that sit on a single album or match a dashboard-only blocklist. Never changes what is sent to jev."""

# Dashboard-only and uncertain: people/band-name tags that clean_tags keeps. The definite noise (favourites, owned,
# junk, ratings, labels, ...) lives in bucketer/tags.py and never reaches here. Nationalities/countries are kept.
NOISE_TAGS = frozenset({
    "steve albini", "les claypool", "josh homme", "dave grohl", "brant bjork", "jello biafra", "mike patton", "ozzy", "dio",
    "ronnie james dio", "dave mustaine", "joe satriani", "satriani", "perry farrell", "debbie harry", "deborah harry", "tool",
    "primus", "pinback", "jack white", "devin townsend", "chuck schuldiner", "steve vai", "kim deal", "rick rubin", "albini",
    "ian mackaye", "paul gilbert", "pete sandoval", "david bowie", "the smiths", "police", "elo", "nirvana", "pantera",
    "motorhead", "u2", "pearl jam", "kyuss", "creed", "nickelback", "zappa", "rush", "foo fighters", "pixies",
})
NOISE_LIMIT = 300  # rows kept; the counts always cover every flagged tag


def noise_audit(records: list[dict]) -> dict:
    holders: dict[str, list[dict]] = {}
    for r in records:
        for t in r["tags"]:
            holders.setdefault(t["name"], []).append(r)
    rows = []
    for tag, albums in holders.items():
        reasons = (["blocklist"] if tag in NOISE_TAGS else []) + (["single album"] if len(albums) == 1 else [])
        if reasons:
            rows.append({"tag": tag, "albums": len(albums), "songs": sum(r["songs"] for r in albums), "reasons": reasons,
                         "example": f"{albums[0]['artist']} - {albums[0]['album']}"})
    rows.sort(key=lambda x: ("blocklist" not in x["reasons"], -x["songs"], x["tag"]))
    return {"tags": len(holders), "flagged": len(rows), "blocklist": sum("blocklist" in x["reasons"] for x in rows),
            "single": sum("single album" in x["reasons"] for x in rows), "rows": rows[:NOISE_LIMIT]}
