import unittest
from typing import ClassVar
from unittest import mock

from bucketer.dashboard import analysis as analysis_module
from bucketer.dashboard import analyze
from bucketer.formatting import coverage_stats
from bucketer.models import Enrichment, Group


def pair(artist, album, album_tags=None, artist_tags=None, songs=1, cover="", date=""):
    def tags(items):
        return [{"name": n, "count": c} for n, c in items] if items else None

    return (Group(key=f"{artist}|{album}", artist=artist, album=album, release_date=date, rows=list(range(songs))),
            Enrichment(album_tags=tags(album_tags), artist_tags=tags(artist_tags), cover=cover))


class QualityTest(unittest.TestCase):
    PAIRS: ClassVar[list] = [
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
        pairs = [pair("A", "1", album_tags=[("stoner rock", 100), ("nirvana", 90), ("gloomy", 80)], songs=2),
                 pair("B", "2", album_tags=[("stoner rock", 100), ("nirvana", 90)], songs=1)]
        noise = analyze(pairs)["noise"]
        rows = {r["tag"]: r for r in noise["rows"]}
        self.assertEqual(set(rows), {"nirvana", "gloomy"})
        self.assertEqual(rows["nirvana"]["reasons"], ["blocklist"])
        self.assertEqual(rows["gloomy"]["reasons"], ["single album"])
        self.assertEqual(noise["rows"][0]["tag"], "nirvana")
        self.assertEqual((noise["tags"], noise["flagged"], noise["blocklist"], noise["single"]), (3, 2, 1, 1))

    def test_blocklisted_single_album_tag_has_both_reasons(self):
        noise = analyze([pair("A", "1", album_tags=[("pantera", 100)])])["noise"]
        self.assertEqual(noise["rows"][0]["reasons"], ["blocklist", "single album"])

    def test_empty_input(self):
        self.assertEqual(analyze([])["noise"]["flagged"], 0)


class DecadeTest(unittest.TestCase):
    def setUp(self):
        for name in ("MIN_CLUSTER_ALBUMS", "MIN_CLUSTER_SONGS", "MIN_TAG_ALBUMS"):
            patcher = mock.patch.object(analysis_module, name, 1)
            patcher.start()
            self.addCleanup(patcher.stop)

    def pairs(self):
        dates = ["1994-05-01", "1996", "1999-01-01", "1991", "1998-02-02", "2012-01-01", "", "0000-00-00", "garbage"]
        return [pair(f"A{i}", "x", album_tags=[("stoner rock", 100)], date=d) for i, d in enumerate(dates)]

    def test_histogram_counts_decades_and_undated(self):
        s = analyze(self.pairs())["decades"]
        self.assertEqual(s["decades"], [1990, 2000, 2010])
        self.assertEqual(s["overall"], {"counts": [5, 0, 1], "unknown": 3})

    def test_cluster_dominated_by_one_decade(self):
        s = analyze(self.pairs())["decades"]
        c = s["clusters"][0]
        self.assertEqual((c["seed"], c["counts"], c["dated"], c["top_decade"]), ("stoner rock", [5, 0, 1], 6, 1990))
        self.assertTrue(c["dominated"])

    def test_small_or_mixed_clusters_are_not_flagged(self):
        few = analyze([pair("A", "1", album_tags=[("x", 100)], date="1990"), pair("B", "2", album_tags=[("x", 100)], date="1991")])
        self.assertFalse(few["decades"]["clusters"][0]["dominated"])
        mixed = analyze([pair(f"A{i}", "1", album_tags=[("x", 100)], date=d) for i, d in enumerate(["1970", "1980", "1990", "2000", "2010", "2020"])])
        self.assertFalse(mixed["decades"]["clusters"][0]["dominated"])

    def test_no_usable_dates(self):
        s = analyze([pair("A", "1", album_tags=[("x", 100)], date="n/a")])["decades"]
        self.assertEqual((s["decades"], s["clusters"], s["overall"]["unknown"]), ([], [], 1))


if __name__ == "__main__":
    unittest.main()
