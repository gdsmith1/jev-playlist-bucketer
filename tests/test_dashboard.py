import json
import os
import re
import tempfile
import unittest
from unittest import mock

from bucketer.dashboard import analysis as analysis_module
from bucketer.dashboard import UMBRELLA_TAGS, album_tags, analyze, render, write_dashboard
from bucketer.dashboard.analysis import release_year
from bucketer.models import Enrichment, Group


def pair(artist, album, tags, songs=1, artist_tags=None):
    return (Group(key=f"{artist}|{album}", artist=artist, album=album, release_date="", rows=list(range(songs))),
            Enrichment(album_tags=[{"name": n, "count": c} for n, c in tags] if tags is not None else None,
                       artist_tags=[{"name": n, "count": c} for n, c in artist_tags] if artist_tags else None))


PAIRS = [
    pair("Kyuss", "Wretch", [("stoner rock", 100), ("desert rock", 60)], songs=3),
    pair("Sleep", "Dopesmoker", [("stoner rock", 100), ("doom metal", 80)], songs=2),
    pair("Electric Wizard", "Dopethrone", [("doom metal", 100), ("stoner rock", 50)]),
    pair("Joy Division", "Closer", [("post-punk", 100)]),
    pair("Nobody", "Nothing", None),
]


class DashboardTest(unittest.TestCase):
    def setUp(self):
        for name in ("MIN_CLUSTER_ALBUMS", "MIN_CLUSTER_SONGS", "MIN_TAG_ALBUMS"):
            patcher = mock.patch.object(analysis_module, name, 1)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_album_tags_merges_levels_and_drops_weak(self):
        _, e = pair("a", "b", [("x", 100), ("faint", 5)], artist_tags=[("x", 40), ("y", 0)])
        self.assertEqual(album_tags(e), {"x": 1.0, "y": 0.5})

    def test_tag_frequency_counts_songs(self):
        a = analyze(PAIRS)
        stoner = next(t for t in a["tags"] if t["tag"] == "stoner rock")
        self.assertEqual((stoner["albums"], stoner["songs"]), (3, 6))
        self.assertEqual(a["tags"][0]["tag"], "stoner rock")

    def test_related_tags_cluster_together(self):
        a = analyze(PAIRS)
        cluster = next(c for c in a["clusters"] if "stoner rock" in c["tags"])
        self.assertIn("doom metal", cluster["tags"])
        self.assertNotIn("post-punk", cluster["tags"])

    def test_umbrella_tags_never_seed_or_join_buckets(self):
        pairs = [pair("A", "1", [("rock", 100), ("stoner rock", 90)], songs=5), pair("B", "2", [("rock", 100), ("doom metal", 90)], songs=5),
                 pair("C", "3", [("rock", 100), ("stoner rock", 80)], songs=5)]
        a = analyze(pairs)
        clustered = {t for c in a["clusters"] for t in c["tags"]}
        self.assertNotIn("rock", clustered)
        self.assertIn("rock", UMBRELLA_TAGS)
        rock = next(t for t in a["tags"] if t["tag"] == "rock")
        self.assertTrue(rock["umbrella"])
        self.assertEqual(rock["songs"], 15)  # still counted in Top tags
        self.assertNotIn("rock", a["heat_tags"])

    def test_heat_matrix_is_square_and_labelled(self):
        a = analyze(PAIRS)
        self.assertEqual(len(a["heat"]), len(a["heat_tags"]))
        self.assertTrue(all(len(r) == len(a["heat_tags"]) for r in a["heat"]))
        i, j = a["heat_tags"].index("stoner rock"), a["heat_tags"].index("doom metal")
        self.assertEqual(a["heat"][i][j], a["heat"][j][i])
        self.assertGreater(a["heat"][i][j], 0)

    def test_album_with_only_umbrella_tags_is_flagged(self):
        a = analyze(PAIRS + [pair("Generic", "Band", [("rock", 100), ("pop", 80)])])
        o = next(o for o in a["outliers"] if o["artist"] == "Generic")
        self.assertEqual(o["reason"], "only umbrella tags")

    def test_covers_flow_to_clusters_and_outliers(self):
        pairs = [pair("A", "1", [("stoner rock", 100)], songs=3), pair("B", "2", [("stoner rock", 90)]), pair("C", "3", None)]  # untagged, so always an outlier
        pairs[0][1].cover, pairs[2][1].cover = "a.jpg", "c.jpg"
        a = analyze(pairs)
        stoner = next(c for c in a["clusters"] if "stoner rock" in c["tags"])
        self.assertEqual(stoner["covers"], [{"url": "a.jpg", "title": "A - 1"}])  # B has no cover, so it is skipped
        self.assertEqual(next(o for o in a["outliers"] if o["artist"] == "C")["cover"], "c.jpg")

    def test_untagged_albums_are_outliers(self):
        a = analyze(PAIRS)
        reasons = {o["artist"]: o["reason"] for o in a["outliers"]}
        self.assertEqual(reasons["Nobody"], "untagged")
        self.assertNotIn("Kyuss", reasons)

    def test_empty_input(self):
        a = analyze([])
        self.assertEqual((a["albums"], a["songs"], a["clusters"], a["outliers"]), (0, 0, [], []))

    def test_render_embeds_json_and_escapes_script_close(self):
        html = render(analyze([pair("</script><b>", "x", [("t", 100)])]), {"t": {"summary": "</script>", "reach": 1}})
        self.assertEqual(html.count("</script>"), 1)  # only the page's own closing tag
        embedded = re.search(r"const D=(.*?);const COLORS", html, re.S).group(1)
        self.assertEqual(json.loads(embedded)["info"]["t"]["summary"], "</script>")

    def test_album_records_cover_every_album(self):
        a = analyze(PAIRS)
        self.assertEqual(len(a["album_records"]), len(PAIRS))
        kyuss = a["album_records"][0]
        self.assertEqual((kyuss["artist"], kyuss["songs"], kyuss["release_year"]), ("Kyuss", 3, None))
        self.assertEqual(kyuss["tags"][0], {"name": "stoner rock", "weight": 1.0, "source": "album"})
        self.assertEqual(set(kyuss["cluster_fits"]), {c["seed"] for c in a["clusters"]})
        self.assertEqual(kyuss["best_cluster"], "stoner rock")
        self.assertTrue(kyuss["has_album_tags"])
        self.assertFalse(kyuss["has_artist_tags"])

    def test_album_record_without_tags_and_artist_source(self):
        a = analyze([pair("a", "b", None, artist_tags=[("x", 90)]), PAIRS[-1]])
        artist_only, nothing = a["album_records"]
        self.assertEqual(artist_only["tags"][0]["source"], "artist")
        self.assertEqual((artist_only["has_album_tags"], artist_only["has_artist_tags"]), (False, True))
        self.assertEqual((nothing["tags"], nothing["best_cluster"], nothing["second_best_cluster"]), ([], None, None))

    def test_release_year_is_parsed_defensively(self):
        self.assertEqual([release_year(d) for d in ("2004-05-01", "1999", "", "0000-00-00", "n/a", "12345")], [2004, 1999, None, None, None, None])

    def test_write_dashboard_fetches_info_for_top_tags(self):
        asked = []
        with tempfile.TemporaryDirectory() as tmp:
            path = write_dashboard(tmp, PAIRS, lambda t: asked.append(t) or ({"summary": "Heavy.", "reach": 2} if t == "stoner rock" else None))
            self.assertEqual(path, os.path.join(tmp, "dashboard.html"))
            with open(path, encoding="utf-8") as f:
                self.assertIn("Heavy.", f.read())
        self.assertIn("doom metal", asked)


class ClusterLimitsTest(unittest.TestCase):
    def test_cluster_count_is_capped_and_overflow_tags_are_left_out(self):
        pairs = [pair(f"A{i}", "x", [(f"tag{i}", 100)], songs=2) for i in range(5) for _ in range(3)]
        with mock.patch.object(analysis_module, "MAX_CLUSTERS", 3), mock.patch.object(analysis_module, "MIN_CLUSTER_ALBUMS", 1), \
                mock.patch.object(analysis_module, "MIN_CLUSTER_SONGS", 1):
            a = analyze(pairs)
        self.assertEqual(len(a["clusters"]), 3)
        self.assertEqual(sum(len(c["tags"]) for c in a["clusters"]), 3)  # tag3 and tag4 attach nowhere

    def test_small_clusters_are_not_suggested(self):
        pairs = [pair(f"A{i}", "x", [("big", 100)], songs=5) for i in range(10)] + [pair("B", "y", [("tiny", 100)]) for _ in range(3)]
        a = analyze(pairs)
        self.assertEqual([c["seed"] for c in a["clusters"]], ["big"])
        with mock.patch.object(analysis_module, "MIN_CLUSTER_ALBUMS", 2), mock.patch.object(analysis_module, "MIN_CLUSTER_SONGS", 2):
            self.assertEqual({c["seed"] for c in analyze(pairs)["clusters"]}, {"big", "tiny"})

    def test_rare_tags_are_not_bucket_candidates(self):
        a = analyze([pair("A", "1", [("one off", 100)], songs=50)])
        self.assertEqual(a["clusters"], [])
        self.assertIn("one off", [t["tag"] for t in a["tags"]])  # still listed in Top tags

    def test_unrelated_tag_never_attaches_at_zero_similarity(self):
        pairs = [pair(f"A{i}", "x", [("alpha", 100)], songs=5) for i in range(10)] + [pair(f"B{i}", "y", [("beta", 100)], songs=5) for i in range(9)]
        with mock.patch.object(analysis_module, "MAX_CLUSTERS", 1):
            a = analyze(pairs)
        self.assertEqual([c["tags"] for c in a["clusters"]], [["alpha"]])

    def test_thirty_clusters_fit_in_one_analysis(self):
        pairs = [pair(f"A{i}-{j}", "x", [(f"tag{i}", 100)], songs=3) for i in range(35) for j in range(10)]
        a = analyze(pairs)
        self.assertEqual(len(a["clusters"]), 30)


if __name__ == "__main__":
    unittest.main()
