import os
import tempfile
import unittest
from unittest import mock

from providers import lastfm
from providers.lastfm import Provider


def tags_resp(*pairs, **attr):
    return {"toptags": {"tag": [{"name": n, "count": c} for n, c in pairs], "@attr": attr}}


def info_resp(listeners="1000", playcount="5000", similar=("a", "b", "c", "d", "e", "f")):
    return {"artist": {"name": "Kyuss", "stats": {"listeners": listeners, "playcount": playcount},
                       "similar": {"artist": [{"name": s} for s in similar]}, "bio": {"summary": "LONG"}}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"LASTFM_API_KEY": "k"})
        env.start()
        self.addCleanup(env.stop)
        self.sleeps = []
        self.p = Provider(cache_dir=self.tmp.name, sleep=self.sleeps.append)
        self.p.throttle = mock.Mock()
        self.calls = []

    def script(self, fn):
        def fake(client, url, *, params=None, **kw):
            self.calls.append(params)
            return fn(params)
        patcher = mock.patch.object(lastfm, "http_get_json", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def methods(self):
        return [c["method"] for c in self.calls]


class LastfmTest(Base):
    def test_missing_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                Provider(cache_dir=self.tmp.name)

    def test_full_fetch_and_tag_cleanup(self):
        def fn(p):
            m = p["method"]
            if m == "track.getTopTags":
                return 200, tags_resp(("Stoner Rock", 100), ("1991", 50), ("seen live", 40), track="hwy 74")
            if m == "album.getTopTags":
                return 200, tags_resp(("stoner metal", 100))
            if m == "artist.getTopTags":
                return 200, tags_resp(("stoner rock", 100))
            return 200, info_resp()
        self.script(fn)
        e = self.p.fetch("Kyuss", "Hwy 74", "Wretch", "x")
        self.assertEqual([t["name"] for t in e["levels"]["track"]["tags"]], ["stoner rock"])
        self.assertEqual(e["matched"]["track"], "hwy 74")
        self.assertEqual(e["extras"]["artist_listeners"], 1000)
        self.assertEqual(len(e["extras"]["similar_artists"]), 5)
        self.assertNotIn("bio", str(e))

    def test_retry_with_cleaned_then_original_and_not_found_cached(self):
        def fn(p):
            if p["method"] == "track.getTopTags":
                return 200, (tags_resp(("rock", 100)) if p["track"] == "Song (Remastered)" else tags_resp())
            return 200, {"error": 6, "message": "nf"}
        self.script(fn)
        e = self.p.fetch("Band", "Song (Remastered)", "Unknown", "")
        self.assertEqual(e["levels"]["track"]["tags"][0]["name"], "rock")
        self.assertEqual([c["track"] for c in self.calls if c["method"] == "track.getTopTags"], ["Song", "Song (Remastered)"])
        self.assertIsNone(e["levels"]["album"])
        self.assertIsNone(e["levels"]["artist"])
        self.assertIn("band|song (remastered)", self.p.cache.section("track"))
        self.assertIsNone(self.p.cache.section("album")["band|unknown"])
        self.assertNotIn("album.getTopTags", self.methods())  # unknown album skipped
        self.assertEqual(self.p.stats["errors"], 0)

    def test_error_not_cached(self):
        self.script(lambda p: (200, {"error": 10, "message": "bad key"}))
        e = self.p.fetch("Band", "Song", "Alb", "")
        self.assertEqual(e["levels"], {"track": None, "album": None, "artist": None})
        self.assertEqual(self.p.stats["errors"], 3)
        self.assertEqual(self.p.cache.section("artist"), {})
        self.assertEqual(self.p.cache.section("track"), {})

    def test_rate_limit_backoff_then_success(self):
        state = {"n": 0}
        def fn(p):
            state["n"] += 1
            if state["n"] <= 2:
                return 200, {"error": 29, "message": "rate"}
            return 200, tags_resp(("rock", 100))
        self.script(fn)
        status, tags, _ = self.p._top_tags("artist.getTopTags", [("artist", "x")])
        self.assertEqual(status, lastfm.OK)
        self.assertEqual(self.sleeps, [2.0, 4.0])

    def test_rate_limit_persistent_is_error(self):
        self.script(lambda p: (200, {"error": 29}))
        status, _ = self.p._call("artist.getInfo", artist="x")
        self.assertEqual(status, lastfm.ERROR)
        self.assertEqual(self.p.stats["calls"], 5)

    def test_http_failure_is_error(self):
        self.script(lambda p: (503, None))
        self.assertEqual(self.p._call("artist.getInfo", artist="x")[0], lastfm.ERROR)

    def test_artist_shared_across_songs(self):
        def fn(p):
            return 200, info_resp() if p["method"] == "artist.getInfo" else tags_resp(("rock", 100))
        self.script(fn)
        self.p.fetch("Kyuss", "A", "X", "")
        self.p.fetch("Kyuss; Someone", "B", "Y", "")
        self.assertEqual(self.methods().count("artist.getTopTags"), 1)
        self.assertEqual(self.methods().count("artist.getInfo"), 1)
        self.assertGreaterEqual(self.p.stats["cache_hits"], 1)

    def test_flush_roundtrip(self):
        self.script(lambda p: (200, info_resp() if p["method"] == "artist.getInfo" else tags_resp(("rock", 100))))
        self.p.fetch("Kyuss", "A", "X", "")
        self.p.flush()
        p2 = Provider(cache_dir=self.tmp.name)
        self.assertIn("kyuss", p2.cache.section("artist"))


if __name__ == "__main__":
    unittest.main()
