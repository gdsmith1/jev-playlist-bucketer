import json
import os
import re
import tempfile
import unittest

from bucketer.dashboard import UMBRELLA_TAGS, album_tags, analyze, render, write_dashboard
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

    def test_write_dashboard_fetches_info_for_top_tags(self):
        asked = []
        with tempfile.TemporaryDirectory() as tmp:
            path = write_dashboard(tmp, PAIRS, lambda t: asked.append(t) or ({"summary": "Heavy.", "reach": 2} if t == "stoner rock" else None))
            self.assertEqual(path, os.path.join(tmp, "dashboard.html"))
            with open(path, encoding="utf-8") as f:
                self.assertIn("Heavy.", f.read())
        self.assertIn("doom metal", asked)


if __name__ == "__main__":
    unittest.main()
