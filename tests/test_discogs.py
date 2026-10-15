import os
import tempfile
import unittest
from unittest import mock

from providers import discogs
from providers.discogs import Provider, norm, title_matches


def resp(status, data=None, headers=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = data
    r.headers = headers or {}
    return r


def master(title, style=("Stoner Rock",), genre=("Rock",), **kw):
    return {"title": title, "style": list(style), "genre": list(genre), "thumb": "x",
            "barcode": ["1"], "community": {"have": 10, "want": 5}, "year": "1991", **kw}


class DiscogsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"DISCOGS_TOKEN": "tok"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.session = mock.Mock()
        self.sleeps = []
        self.p = Provider(self.tmp.name, session=self.session, sleep=self.sleeps.append)

    def test_missing_token(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                Provider(self.tmp.name)

    def test_title_match(self):
        self.assertTrue(title_matches("Kyuss - Wretch", "Kyuss", "Wretch"))
        self.assertTrue(title_matches("Kyuss (2) - Wretch!", "kyuss", "wretch"))
        self.assertFalse(title_matches("Other - Thing", "Kyuss", "Wretch"))
        self.assertEqual(norm("A.B-c"), "a b c")

    def test_album_master_styles_first_and_noise_stripped(self):
        self.session.get.side_effect = [
            resp(200, {"results": [master("Kyuss - Wretch")]}),
            resp(200, {"results": [master("Kyuss - Wretch")]}),
            resp(200, {"results": []}),
        ]
        e = self.p.fetch("Kyuss", "Katzenjammer", "Wretch (Deluxe Edition)", "")
        self.assertEqual(e["levels"]["album"]["genres"], ["stoner rock", "rock"])
        self.assertEqual(e["extras"], {"year": 1991, "have": 10, "want": 5})
        cached = self.p.cache.section("album")["kyuss|wretch"]
        self.assertNotIn("thumb", str(cached))
        self.assertLessEqual(self.session.get.call_count, 3)

    def test_release_fallback_union_and_format(self):
        r1 = master("A - B", style=("Grunge",), format=["Vinyl", "LP", "Album"])
        r2 = master("A - B", style=("Indie Rock", "Grunge"), genre=("Rock",))
        junk = master("Z - Y", style=("Pop",))
        self.session.get.side_effect = [
            resp(200, {"results": []}),
            resp(200, {"results": [r1, junk, r2]}),
        ]
        ok, level = self.p._lookup_album("A", "B")
        self.assertTrue(ok)
        self.assertEqual(level["genres"], ["grunge", "rock", "indie rock"])
        self.assertEqual(level["extras"]["format"], "Album")

    def test_not_found_cached_error_not_cached(self):
        self.session.get.side_effect = [resp(200, {"results": []})] * 2
        self.assertIsNone(self.p._cached("album", "k", lambda: self.p._lookup_album("A", "B")))
        self.assertIn("k", self.p.cache.section("album"))
        self.assertIsNone(self.p.cache.section("album")["k"])
        self.session.get.reset_mock()
        self.assertIsNone(self.p._cached("album", "k", lambda: self.fail("should be cached")))
        self.assertEqual(self.p.stats["cache_hits"], 1)

        self.session.get.side_effect = [resp(500, {})] * 10
        self.assertIsNone(self.p._cached("album", "e", lambda: self.p._lookup_album("A", "B")))
        self.assertNotIn("e", self.p.cache.section("album"))
        self.assertEqual(self.p.stats["errors"], 1)

    def test_artist_derived_top5_and_shared_cache(self):
        results = [master("Kyuss - A", style=("Stoner Rock",)), master("Kyuss - B", style=("Stoner Rock", "Hard Rock")),
                   master("Someone Else - C", style=("Pop Rap",))]
        self.session.get.side_effect = [resp(200, {"results": results})]
        ok, level = self.p._lookup_artist("Kyuss")
        self.assertEqual(level["genres"], ["stoner rock", "rock", "hard rock"])
        self.assertEqual(level["tags"], [])
        # shared across songs: second fetch for same artist makes no artist call
        self.session.get.side_effect = [resp(200, {"results": results})] + [resp(200, {"results": []})] * 6
        self.p.fetch("Kyuss", "", "", "")
        n = self.session.get.call_count
        self.p.fetch("Kyuss feat. X", "", "", "")
        self.assertEqual(self.session.get.call_count, n)

    def test_track_guard(self):
        good = master("Band - Song Title", style=("Punk",))
        junk = master("Band - Totally Unrelated EP", style=("Pop",))
        self.session.get.side_effect = [resp(200, {"results": [junk, good]})]
        ok, level = self.p._lookup_track("Band", "Song Title", "Some Album")
        self.assertEqual(level["genres"], ["punk", "rock"])
        self.session.get.side_effect = [resp(200, {"results": [junk]})]
        self.assertEqual(self.p._lookup_track("Band", "Song Title", "Some Album"), (True, None))

    def test_call_budget_per_song(self):
        self.session.get.return_value = resp(200, {"results": []})
        self.p.fetch("A", "T", "B", "")
        # album master + release fallback + artist = 3, track skipped
        self.assertEqual(self.session.get.call_count, 3)

    def test_429_waits_60_then_retries(self):
        self.session.get.side_effect = [resp(429, {}), resp(200, {"results": []})]
        ok, results = self.p._search({"type": "master"})
        self.assertTrue(ok)
        self.assertIn(60.0, self.sleeps)
        self.assertEqual(self.session.get.call_count, 2)

    def test_low_remaining_sleeps(self):
        self.session.get.side_effect = [
            resp(200, {"results": []}, {"X-Discogs-Ratelimit-Remaining": "1"}),
            resp(200, {"results": []}, {"X-Discogs-Ratelimit-Remaining": "50"}),
        ]
        self.p._search({})
        self.assertNotIn(60.0, self.sleeps)
        self.p._search({})
        self.assertIn(60.0, self.sleeps)

    def test_auth_headers(self):
        self.session.get.return_value = resp(200, {"results": []})
        self.p._search({})
        h = self.session.get.call_args.kwargs["headers"]
        self.assertEqual(h["Authorization"], "Discogs token=tok")


if __name__ == "__main__":
    unittest.main()
