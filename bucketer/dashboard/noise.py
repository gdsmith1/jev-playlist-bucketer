"""Tag noise audit: tags that sit on a single album or match a dashboard-only blocklist. Never changes what is sent to jev."""

# Dashboard-only: not applied by clean_tags, so jev text and cache keys are unaffected. Edit freely.
NOISE_TAGS = frozenset({
    "k1r7m", "kaufekaufenkaufen", "pwnage", "jb recommendation", "randomvalue", "sftri", "queued", "liblistened", "my cds", "rock-avg", "rock-good",
    "american", "british", "english", "swedish", "german", "french", "finnish", "norwegian", "danish", "dutch", "canadian", "australian", "irish",
    "scottish", "welsh", "italian", "spanish", "japanese", "usa", "uk", "united states", "sweden", "germany", "france", "finland", "norway", "denmark",
    "canada", "australia", "ireland", "scotland", "japan", "seen live", "favorites", "favourites", "albums i own", "cover",
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
