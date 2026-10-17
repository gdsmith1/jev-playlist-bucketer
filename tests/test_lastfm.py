import os
import tempfile
import unittest
from unittest import mock

import requests

from bucketer import lastfm
from bucketer.lastfm import LastfmClient, Throttle


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
        self.p = LastfmClient(cache_dir=self.tmp.name, sleep=self.sleeps.append)
        self.p.throttle = mock.Mock()
        self.calls = []

    def script(self, fn):
        def fake(params):
            self.calls.append(params)
            return fn(params)
        patcher = mock.patch.object(LastfmClient, "_get_json", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def methods(self):
        return [c["method"] for c in self.calls]


class LastfmTest(Base):
    def test_missing_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                LastfmClient(cache_dir=self.tmp.name)

    def test_full_fetch_and_tag_cleanup(self):
        def fn(p):
            m = p["method"]
            if m == "album.getTopTags":
                return 200, tags_resp(("Stoner Metal", 100), ("1991", 50), ("seen live", 40), ("Wretch", 30), ("reissue", 20))
            if m == "artist.getTopTags":
                return 200, tags_resp(("stoner rock", 100), ("Kyuss", 90))
            return 200, info_resp()
        self.script(fn)
        e = self.p.fetch("Kyuss", "Wretch (Deluxe Edition)")
        self.assertEqual([t["name"] for t in e.album_tags], ["stoner metal"])
        self.assertEqual([t["name"] for t in e.artist_tags], ["stoner rock"])
        self.assertEqual(e.similar_artists, ["a", "b", "c", "d", "e"])
        self.assertNotIn("track.getTopTags", self.methods())
        self.assertNotIn("bio", str(e))

    def test_album_retry_cleaned_then_original_and_not_found_cached(self):
        def fn(p):
            if p["method"] == "album.getTopTags":
                return 200, (tags_resp(("grunge", 100)) if p["album"] == "Alb (Deluxe Edition)" else tags_resp())
            return 200, {"error": 6, "message": "nf"}
        self.script(fn)
        e = self.p.fetch("Band", "Alb (Deluxe Edition)")
        self.assertEqual(e.album_tags[0]["name"], "grunge")
        self.assertEqual([c["album"] for c in self.calls if c["method"] == "album.getTopTags"], ["Alb", "Alb (Deluxe Edition)"])
        self.assertIsNone(e.artist_tags)
        self.assertIn("band", self.p.cache.section("artist"))
        self.assertEqual(self.p.stats["errors"], 0)

    def test_unknown_album_skips_lookup(self):
        self.script(lambda p: (200, {"error": 6, "message": "nf"}))
        e = self.p.fetch("Band", "Unknown")
        self.assertIsNone(e.album_tags)
        self.assertNotIn("album.getTopTags", self.methods())

    def test_deluxe_and_plain_album_share_cache(self):
        self.script(lambda p: (200, info_resp() if p["method"] == "artist.getInfo" else tags_resp(("grunge", 100))))
        self.p.fetch("Band", "Alb")
        self.p.fetch("Band", "Alb (Remastered 2009)")
        self.assertEqual(self.methods().count("album.getTopTags"), 1)

    def test_error_not_cached(self):
        self.script(lambda p: (200, {"error": 10, "message": "bad key"}))
        e = self.p.fetch("Band", "Alb")
        self.assertEqual((e.album_tags, e.artist_tags), (None, None))
        self.assertEqual(self.p.stats["errors"], 2)
        self.assertEqual(self.p.cache.section("artist"), {})
        self.assertEqual(self.p.cache.section("album"), {})

    def test_rate_limit_backoff_then_success(self):
        state = {"n": 0}
        def fn(p):
            state["n"] += 1
            if state["n"] <= 2:
                return 200, {"error": 29, "message": "rate"}
            return 200, tags_resp(("rock", 100))
        self.script(fn)
        status, tags = self.p._top_tags("artist.getTopTags", [("artist", "x")])
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
        self.p.fetch("Kyuss", "X")
        self.p.fetch("Kyuss; Someone", "Y")
        self.assertEqual(self.methods().count("artist.getTopTags"), 1)
        self.assertEqual(self.methods().count("artist.getInfo"), 1)
        self.assertGreaterEqual(self.p.stats["cache_hits"], 1)

    def test_flush_roundtrip(self):
        self.script(lambda p: (200, info_resp() if p["method"] == "artist.getInfo" else tags_resp(("rock", 100))))
        self.p.fetch("Kyuss", "X")
        self.p.flush()
        p2 = LastfmClient(cache_dir=self.tmp.name)
        self.assertIn("kyuss", p2.cache.section("artist"))


class ThrottleTest(unittest.TestCase):
    def test_spaces_calls(self):
        now = [100.0]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        throttle = Throttle(1.0, clock=lambda: now[0], sleep=sleep)
        throttle.wait()  # first call never sleeps
        now[0] += 0.25
        throttle.wait()
        now[0] += 5
        throttle.wait()  # already past the interval
        self.assertEqual(sleeps, [0.75])


class GetJsonTest(Base):
    def resp(self, status, body=None):
        r = mock.Mock(status_code=status)
        if body is None:
            r.json.side_effect = ValueError("no json")
        else:
            r.json.return_value = body
        return r

    def test_success_and_throttled(self):
        self.p.session = mock.Mock()
        self.p.session.get.return_value = self.resp(200, {"ok": 1})
        self.assertEqual(self.p._get_json({"a": 1}), (200, {"ok": 1}))
        self.p.throttle.wait.assert_called_once()
        self.assertIn("timeout", self.p.session.get.call_args.kwargs)

    def test_network_error_never_raises(self):
        self.p.session = mock.Mock()
        self.p.session.get.side_effect = requests.ConnectionError("down")
        self.assertEqual(self.p._get_json({}), (0, None))

    def test_non_json_body(self):
        self.p.session = mock.Mock()
        self.p.session.get.return_value = self.resp(503)
        self.assertEqual(self.p._get_json({}), (503, None))

    def test_retry_adapter_is_mounted_for_transient_statuses(self):
        adapter = self.p.session.get_adapter(lastfm.LASTFM_URL)
        self.assertEqual(adapter.max_retries.total, 4)
        self.assertIn(429, adapter.max_retries.status_forcelist)
        self.assertIn(503, adapter.max_retries.status_forcelist)


if __name__ == "__main__":
    unittest.main()
