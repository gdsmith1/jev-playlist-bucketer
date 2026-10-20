import unittest

from bucketer.dashboard import analyze
from bucketer.formatting import coverage_stats
from bucketer.models import Enrichment, Group


def pair(artist, album, album_tags=None, artist_tags=None, songs=1, cover="", date=""):
    def tags(items):
        return [{"name": n, "count": c} for n, c in items] if items else None

    return (Group(key=f"{artist}|{album}", artist=artist, album=album, release_date=date, rows=list(range(songs))),
            Enrichment(album_tags=tags(album_tags), artist_tags=tags(artist_tags), cover=cover))


class QualityTest(unittest.TestCase):
    PAIRS = [
        pair("A", "1", album_tags=[("x", 100)], songs=4, cover="u"),
        pair("B", "2", artist_tags=[("x", 100)], songs=2),
        pair("C", "3", artist_tags=[("y", 100)], songs=5, cover="u"),
        pair("D", "4", songs=3),
    ]

    def test_counts_split_albums_and_songs(self):
        q = analyze(self.PAIRS)["quality"]
        self.assertEqual(q["total"], {"albums": 4, "songs": 14})
        self.assertEqual(q["album_level"], {"albums": 1, "songs": 4})
        self.assertEqual(q["artist_only"], {"albums": 2, "songs": 7})
        self.assertEqual(q["untagged"], {"albums": 1, "songs": 3})
        self.assertEqual(q["no_cover"], {"albums": 2, "songs": 5})

    def test_artist_only_list_is_ranked_by_songs(self):
        q = analyze(self.PAIRS)["quality"]
        self.assertEqual([r["artist"] for r in q["artist_only_list"]], ["C", "B"])
        self.assertEqual(q["artist_only_list"][0]["tags"], ["y"])

    def test_matches_coverage_stats(self):
        stats = coverage_stats(e for _, e in self.PAIRS)
        q = analyze(self.PAIRS)["quality"]
        self.assertEqual(q["total"]["albums"], stats["albums"])
        self.assertEqual(q["album_level"]["albums"], stats["album"])
        self.assertEqual(q["untagged"]["albums"], stats["none"])
        self.assertEqual(q["album_level"]["albums"] + q["artist_only"]["albums"], stats["any"])


class NoiseTest(unittest.TestCase):
    def test_flags_single_album_and_blocklist_tags(self):
        pairs = [pair("A", "1", album_tags=[("stoner rock", 100), ("swedish", 90), ("gloomy", 80)], songs=2),
                 pair("B", "2", album_tags=[("stoner rock", 100), ("swedish", 90)], songs=1)]
        noise = analyze(pairs)["noise"]
        rows = {r["tag"]: r for r in noise["rows"]}
        self.assertEqual(set(rows), {"swedish", "gloomy"})
        self.assertEqual(rows["swedish"]["reasons"], ["blocklist"])
        self.assertEqual(rows["gloomy"]["reasons"], ["single album"])
        self.assertEqual(noise["rows"][0]["tag"], "swedish")
        self.assertEqual((noise["tags"], noise["flagged"], noise["blocklist"], noise["single"]), (3, 2, 1, 1))

    def test_blocklisted_single_album_tag_has_both_reasons(self):
        noise = analyze([pair("A", "1", album_tags=[("pwnage", 100)])])["noise"]
        self.assertEqual(noise["rows"][0]["reasons"], ["blocklist", "single album"])

    def test_empty_input(self):
        self.assertEqual(analyze([])["noise"]["flagged"], 0)


if __name__ == "__main__":
    unittest.main()
