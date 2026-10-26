import os
import tempfile
import unittest
from unittest import mock

from bucketer.dashboard import analysis as analysis_module
from bucketer.dashboard import analyze, render, write_dashboard
from bucketer.dashboard.jevresults import summarize
from tests.test_dashboard import PAIRS


def rec(artist, songs, buckets, scores, matched):
    return {"artist": artist, "album": "x", "songs": songs, "buckets": buckets, "jev": {"scores": scores, "matched": matched}}


RESULT = {"threshold": 1.0, "buckets": {"stoner": {"description": "d", "source": "recommended"}, "mine": {"description": "", "source": "custom"}}}
RECORDS = [rec("a", 3, ["stoner"], {"stoner": 1.5, "mine": 0.2}, ["stoner"]),
           rec("b", 2, ["stoner"], {"stoner": 0.8, "mine": 1.1}, ["mine"]),
           rec("c", 1, [], {"stoner": 1.2, "mine": 1.3}, ["stoner", "mine"]),
           rec("d", 4, [], {"stoner": 0.1, "mine": 0.0}, [])]


class JevResultsTest(unittest.TestCase):
    def test_counts_reconcile(self):
        s = summarize(RECORDS, RESULT, ["stoner"])
        self.assertEqual(s["other"]["albums"] + s["one"]["albums"] + s["several"]["albums"], len(RECORDS))
        self.assertEqual(s["other"]["songs"] + s["one"]["songs"] + s["several"]["songs"], 10)
        self.assertEqual((s["other"]["albums"], s["one"]["albums"], s["several"]["albums"]), (1, 2, 1))

    def test_agreement_only_for_recommended(self):
        s = summarize(RECORDS, RESULT, ["stoner"])
        stoner, mine = s["buckets"]
        self.assertEqual(stoner["agreement"], {"jev": 2, "tags": 2, "both": 1, "jev_only": 1, "tags_only": 1})
        self.assertNotIn("agreement", mine)
        self.assertEqual(stoner["top"][0]["artist"], "a")

    def test_borderline(self):
        rows = summarize(RECORDS, RESULT, ["stoner"])["borderline"]["rows"]
        self.assertEqual([(r["artist"], r["bucket"]) for r in rows], [("b", "stoner")])


class RenderJevTest(unittest.TestCase):
    def setUp(self):
        for name in ("MIN_CLUSTER_ALBUMS", "MIN_CLUSTER_SONGS", "MIN_TAG_ALBUMS"):
            patcher = mock.patch.object(analysis_module, name, 1)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.result = {"threshold": 1.0, "buckets": {"stoner rock": {"description": "d", "source": "recommended"}},
                       "albums": [{"scores": {"stoner rock": 0.9 if i else 1.2}, "matched": [] if i else ["stoner rock"]} for i in range(len(PAIRS))]}

    def test_record_and_section_only_with_jev(self):
        a = analyze(PAIRS, self.result)
        self.assertEqual(a["album_records"][0]["jev"]["matched"], ["stoner rock"])
        self.assertEqual(a["jev"]["other"]["albums"], len(PAIRS) - 1)
        plain = analyze(PAIRS)
        self.assertNotIn("jev", plain)
        self.assertNotIn("jev", plain["album_records"][0])
        self.assertNotIn('"jev"', render(plain, {}).split("const D=")[1].split(";\nconst $")[0])

    def test_write_dashboard_accepts_result(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_dashboard(d, PAIRS, lambda t: None, self.result)
            self.assertIn("Selected buckets", __import__("pathlib").Path(path).read_text(encoding="utf-8"))
            self.assertTrue(os.path.exists(path))


def song_list(pairs):
    songs = []
    for g, (group, _) in enumerate(pairs):
        songs += [{"index": i, "title": f"t{i}", "artist": group.artist, "album": group.album, "group": g} for i in group.rows]
    return songs


class SongsAndTabsTest(unittest.TestCase):
    def test_song_rows_reconcile_with_album_counts(self):
        a = analyze(PAIRS, songs=song_list(PAIRS))
        self.assertFalse(a["song_rows_per_album"])
        for g, record in enumerate(a["album_records"]):
            self.assertEqual(sum(s["g"] == g for s in a["song_rows"]), record["songs"])
        self.assertEqual(len(a["song_rows"]), a["songs"])

    def test_without_songs_falls_back_to_one_row_per_album(self):
        a = analyze(PAIRS)
        self.assertTrue(a["song_rows_per_album"])
        self.assertEqual([s["g"] for s in a["song_rows"]], list(range(len(PAIRS))))

    def test_song_dicts_from_lines(self):
        from bucketer.dashboard import song_dicts
        from bucketer.models import Group
        lines = ["A , one , X , 2001", "B , two , Y , 2002", "A , three , X , 2001"]
        groups = [Group("a|x", "A", "X", "2001", [0, 2]), Group("b|y", "B", "Y", "2002", [1])]
        self.assertEqual([(s["title"], s["group"]) for s in song_dicts(lines, groups)], [("one", 0), ("two", 1), ("three", 0)])

    def test_page_has_three_tabs_with_and_without_jev(self):
        for result in (None, {"threshold": 1.0, "buckets": {"k": {"description": "", "source": "custom"}},
                              "albums": [{"scores": {"k": 0.5}, "matched": []} for _ in PAIRS]}):
            html = render(analyze(PAIRS, result), {})
            self.assertIn('role="tablist"', html)
            for name in ("recommended", "selected", "playlist"):
                self.assertIn(f'id="panel-{name}"', html)
                self.assertIn(f'data-tab="{name}"', html)
            self.assertIn("ArrowRight", html)
