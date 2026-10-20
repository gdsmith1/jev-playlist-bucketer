"""Last.fm tag cleaning."""

import re
from typing import Iterable

MAX_TAGS_PER_LEVEL = 8

NOISE_TAGS = frozenset(
    {
        # listening state / ownership / collection
        "seen live", "favorites", "favourites", "favorite", "favourite albums", "favorite albums", "fav albums", "fav",
        "favourite album", "favorite album", "my favourite albums", "my favorite albums", "my favorites", "my albums",
        "my music", "my cds", "my cd collection", "my album collection", "home collection", "collection", "owned", "own",
        "own it", "albums i own", "albums owned", "cds i own", "cd i own", "vinyl", "vinyls i own", "vinyl i own",
        "own on vinyl", "own on cd", "have on vinyl", "got it on vinyl", "color vinyl", "crates of vinyl", "i own on vinyl",
        "i own this album", "i have this album", "in vinyl collection", "lps i own", "metal on vinyl", "had this on cassette",
        "cd", "cassette", "spotify", "emusic", "streamable", "not streamable", "fully streamable albums", "download",
        "listened", "listen", "listen again", "liblistened", "queued", "added", "wishlist", "to get", "to buy", "get",
        "albums to buy", "to listen", "to check out", "check out", "need to rate", "i need", "i want", "playlist",
        "albums to listen to", "completed albums log", "current favorites", "desert island discs", "hall of fame",
        "mixtaperoom", "under 2000 listeners",
        # praise / opinion / rating / recommendation
        "awesome", "love", "good", "best", "great", "amazing", "cool", "fucking awesome", "masterpiece", "perfection",
        "underrated", "essential albums", "great albums", "great album", "best albums", "best album", "best albums ever",
        "best records ever", "best eps", "best new reissues", "perfect albums", "classic albums", "iconic albums",
        "milestones", "100 essential albums", "killer album", "i like this", "i love singing along", "recommended",
        "jb recommendation", "yes", "no", "top", "bops", "aoty", "melts face", "great lyrics", "glorious vocals",
        "nice album art", "great album art", "killer bass", "superb song to drive to", "heavy as fuck",
        "these tags suck", "<3", "buenos", "mis albumes favoritos", "favortite albums", "rock-avg", "rock-good",
        "3 star", "9.00/10.00", "all time favorite records", "rivers all time favorite albums",
        # generic / meta
        "all", "albums", "album", "debut album", "debut", "demo", "ep", "studio album", "live album", "live", "compilation",
        "compilation album", "self-titled", "self-titled album", "self titled release", "cover", "covers", "cover album",
        "best hot cover album", "multiple formats", "less than 40 minutes", "memories", "college years", "high school",
        "21st century", "hanging out", "road trip", "late night", "summer", "summery", "june", "autumn",
        # tagger-chatter / junk / unrelated site tags
        "k1r7m", "kaufekaufenkaufen", "kaufenkaufenkaufen", "pwnage", "randomvalue", "sftri", "totec radio", "tremolo radio",
        "registret", "jecks", "opelmelange", "zolo", "sjc", "tewz", "al-hizan", "vinesauce", "adult swim", "superjail",
        "encontro dos famosos", "leapsandalbums", "schnuddel-alben", "favedrums", "pigfuck", "where is my bong",
        "flashback alternatives", "alcohol apocalypse", "kronos mutha fukin klassik", "in search of the lost genre",
        "stairway to hell", "my private work station", "my gang 10", "my crazy diamonds", "my funeral soundtrack",
        "mike portnoy", "tragically yours", "voulez voulez voulez vous", "the peoria years", "post-punk 77 new wave 85",
        "sousaphonic aotm 201102", "brc blues band", "brc blues band karlsruhe", "blues-rockclub", "karlsruhe",
        "stretchsaysabigyesto these albums", "fun to skateboard to", "drunk tank singalong tune",
        "when we were older and our hair was longer", "you know her life was saved by last fm free music player",
        "shows you that swedes are not only good in making furniture", "blacker than the blackest black times infinity",
        "not of this world", "rock and roll party", "growing-up",
        "male vocalists", "female vocalists", "male vocalist", "female vocalist",
        # tail: praise, chatter, meta, test tags
        "test", "testing", "api test", "misstagged", "misspelled", "overrated", "officially shit", "terrible", "bad", "not good",
        "this album sucks", "wow", "check", "finished", "reviewed", "need", "want", "have", "like", "loves", "love it", "love this",
        "perfect", "legend", "legendary", "fantastic", "excellent", "brilliant", "incredible", "wonderful", "lovely", "genius",
        "genious", "exceptional", "ultimate", "solid", "essential", "timeless", "good album", "amazing albums", "awesome albums",
        "fucking great", "fucking amazing", "fucking masterpiece", "the best", "just great", "insane", "badass", "bad ass rock",
        "ok", "win", "original", "new", "the", "x", "d", "w", "f", "go", "with", "mia", "fs", "dm", "dos sux", "single", "singles",
        "split", "split album", "releases", "new releases", "most wanted", "wanted", "wish list", "check it out", "to explore",
        "musthave", "can't live without", "seen in concert", "bands seen live", "saw them live", "good live", "love it",
        "names of people", "rickroll", "international", "title is imperative", "good shit", "good times", "good riffs",
        "eponymous", "misc", "tgif", "records and tapes", "lossless", "discover", "reminisce", "remember", "unclassifiable",
        "tribute album", "cover version", "naked covers", "extended play", "sophomore album", "3rd album", "5th album",
        # labels
        "4ad", "sst", "relapse records", "dischord", "dischord records", "columbia records", "virgin records", "factory records",
        "ipecac recordings", "interscope records", "rise above records", "wax trax", "roadrunner records", "sub pop", "sire",
        "matador records", "jagjaguwar", "beggars banquet records", "spinefarm records", "warner music", "universal music",
        "music for nations", "grand royal",
    }
)

# Prefix/substring patterns for families of noise tags (personal, rating, recommendation, ownership phrasing).
_NOISE_RE = re.compile(
    r"^(my|best|favou?rite|fav|top|great|own|owned|i own|i have|i love|albums? (i|to)|cds? i|vinyls? i|to (get|buy|listen))\b"
    r"|\b(i own|on vinyl|on cd|favou?rites?|favou?rite albums?|albums? owned)$"
    r"|^(tragically yours|allbout|aotm)\b|\b\d+(\.\d+)?/10(\.0+)?$|^\d+ star|^\d{4} (albums|releases)$"
    r"|^\d{1,2}$"
    r"|\b(records|recordings|studios?)$|\b(album )?cover( art)?$|\bnude\b|\bnaked\b|\bboobs\b|recommend|\bfaves?\b|\bfavs?\b"
    r"|\balbums? ever\b|^(just|really|pretty|fucking|so) (love|great|good|amazing)"
)

# Last.fm housekeeping tags. Nationalities and places are kept: where a band is from is useful context.
JUNK_TAGS = frozenset({"wrong track streaming", "reissue", "remaster", "remastered", "deluxe edition"})

# Too generic to characterize an album; kept, but ranked below any specific tag.
VAGUE_TAGS = frozenset({"alternative", "rock", "indie", "pop", "metal", "punk", "electronic", "experimental"})

YEAR_RE = re.compile(r"^\d{4}$")
_DECADE_RE = re.compile(r"^\d{2,4}s$")
# List-membership and chatter tags: "1001 albums you must hear...", "best of 2013", "top metal albums of
# the decade", "allboutguitarcom", and jokes like "a good girlfriend will have sex with me to this music".
_JUNK_RE = re.compile(
    r"^(wrong|incorrect|best of|top )\b|\balbums? (you|i|of|that)\b|\bgirlfriend\b|\b\d{4}\b.*\b\d{4}\b|\w+com$"
)


def tag_key(name: str) -> str:
    """Spelling-insensitive identity: `synth-pop`, `synth pop` and `synthpop` match."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def tag_order(name: str, count: int) -> tuple:
    return (name in VAGUE_TAGS, -count, name)


def clean_tags(tags: Iterable | None, max_n: int = MAX_TAGS_PER_LEVEL, exclude: Iterable[str | None] = ()) -> list[dict]:
    """Normalize `[{"name", "count"}]` (bare strings tolerated, count 0): lowercase,
    drop years/decades, noise, junk and echoes of `exclude` names (artist/album),
    merge spelling variants (best count wins), sort specific tags first then by
    count desc then name, truncate."""
    excluded = {tag_key(n) for n in exclude if n}
    best: dict[str, tuple[str, int]] = {}
    for tag in tags or []:
        if isinstance(tag, str):
            name, count = tag, 0
        else:
            name, count = tag.get("name"), tag.get("count") or 0
        if not name:
            continue
        name = name.strip().lower()
        if (
            not name
            or name in NOISE_TAGS
            or name in JUNK_TAGS
            or _JUNK_RE.search(name)
            or _NOISE_RE.search(name)
            or YEAR_RE.match(name)
            or _DECADE_RE.match(name)
            or tag_key(name) in excluded
        ):
            continue
        key = tag_key(name)
        if key not in best or (count, name) > (best[key][1], best[key][0]):
            best[key] = (name, count)
    ordered = sorted(best.values(), key=lambda item: tag_order(*item))
    return [{"name": name, "count": count} for name, count in ordered[:max_n]]
