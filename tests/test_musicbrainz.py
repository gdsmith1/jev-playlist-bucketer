import os
import tempfile
import unittest
from unittest import mock

from providers import musicbrainz
from providers.musicbrainz import Provider, migrate_legacy


def make(tmp):
    p = Provider(cache_dir=tmp)
    p.throttle = mock.Mock()
    return p


def route(responses):
    """Fake http_get_json keyed on URL suffix; records calls."""
    calls = []

    def fake(client, url, **kw):
        path = url.split("/ws/2/")[1]
        calls.append((path, kw.get("params")))
        for prefix, resp in responses.items():
            if path.startswith(prefix):
                return resp
        return 404, None

    return fake, calls


ISRC = {"recordings": [{"id": "r1"}]}
REC = {"title": "Hwy 74", "genres": [{"name": "Stoner Rock", "count": 2}], "tags": [{"name": "rock", "count": 1}],
       "artist-credit": [{"artist": {"id": "a1"}}]}
RG = {"release-groups": [{"score": 100, "title": "Wretch", "primary-type": "Album", "secondary-types": [],
                          "first-release-date": "1991-09-01", "tags": [{"name": "stoner rock", "count": 5}, {"name": "1991", "count": 3}]}]}
ART = {"name": "Kyuss", "type": "Group", "country": "US", "life-span": {"begin": "1987-01", "ended": True},
       "genres": [{"name": "stoner rock", "count": 13}, {"name": "desert rock", "count": 3}], "tags": [{"name": "seen live", "count": 4}]}


class MigrationTest(unittest.TestCase):
    def test_migrate(self):
        track = {"KEEP": None}
        n = migrate_legacy(track, {
            "A": {"artist": "x", "track": "y", "tags": ["Rock", "Metal"]},
            "B": {"artist": "x", "track": "y", "tags": None},
            "C": {"artist": "x", "track": "y", "tags": []},
            "KEEP": {"tags": ["z"]},
        })
        self.assertEqual(n, 3)
        self.assertEqual(track["A"], {"genres": ["rock", "metal"], "tags": []})
        self.assertIsNone(track["B"])
        self.assertIsNone(track["C"])
        self.assertIsNone(track["KEEP"])

    def test_loaded_on_init_and_not_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "mb_cache.json"), "w") as f:
                f.write('{"I1": {"artist": "a", "track": "t", "tags": ["doom"]}}')
            p = make(tmp)
            fake, calls = route({})
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                e = p.fetch("A", "t", "", "I1")
            self.assertEqual(e["levels"]["track"]["genres"], ["doom"])
            self.assertFalse([c for c in calls if c[0].startswith(("isrc", "recording"))])


class FetchTest(unittest.TestCase):
    def full(self):
        return route({
            "isrc/": (200, ISRC), "recording/": (200, REC), "release-group": (200, RG),
            "artist/a1": (200, ART),
        })

    def test_all_levels_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            fake, calls = self.full()
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                e = p.fetch("Kyuss", "Hwy 74", "Wretch (Remastered)", "ISRC1")
            self.assertLessEqual(len(calls), 4)
            self.assertEqual(e["levels"]["track"]["genres"], ["stoner rock"])
            self.assertEqual([t["name"] for t in e["levels"]["album"]["tags"]], ["stoner rock"])  # year dropped
            self.assertEqual(e["levels"]["artist"]["genres"], ["stoner rock", "desert rock"])
            self.assertEqual(e["levels"]["artist"]["tags"], [])  # noise dropped
            self.assertEqual(e["extras"]["artist_type"], "Group")
            self.assertEqual(e["extras"]["artist_begin"], "1987")
            self.assertTrue(e["extras"]["artist_ended"])
            self.assertEqual(e["extras"]["album_type"], "Album")

    def test_artist_cached_across_songs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            fake, calls = self.full()
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                p.fetch("Kyuss", "A", "Wretch", "I1")
                p.fetch("Kyuss", "B", "Wretch", "I2")
            self.assertEqual(sum(1 for c in calls if c[0].startswith("artist/")), 1)

    def test_artist_search_fallback_score_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            fake, calls = route({"artist?": (200, {"artists": [{"id": "x", "score": 80}]})})
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                e = p.fetch("Nobody", "t", "", "")
            self.assertIsNone(e["levels"]["artist"])
            self.assertIn("Nobody", p.cache.section("artist") and "Nobody".title() or "Nobody")
            self.assertIsNone(p.cache.section("artist")["nobody"])  # not found cached as null

    def test_error_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            fake, _ = route({"isrc/": (503, None), "release-group": (503, None), "artist": (503, None)})
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                e = p.fetch("A", "t", "Alb", "I1")
            self.assertEqual(p.stats["errors"], 3)
            self.assertEqual(e["levels"], {"track": None, "album": None, "artist": None})
            self.assertEqual(p.cache.section("track"), {})
            self.assertEqual(p.cache.section("artist"), {})

    def test_not_found_cached_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            fake, _ = route({"release-group": (200, {"release-groups": []}), "artist?": (200, {"artists": []})})
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                p.fetch("A", "t", "Alb", "I1")  # isrc 404 -> not found
            self.assertIsNone(p.cache.section("track")["I1"])
            self.assertIn("a|alb", p.cache.section("album"))
            self.assertIsNone(p.cache.section("album")["a|alb"])

    def test_album_retry_with_original_and_live_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make(tmp)
            live = {"release-groups": [{"score": 100, "title": "x", "primary-type": "Album", "secondary-types": ["Live"], "tags": []}]}
            fake, calls = route({"release-group": (200, live)})
            with mock.patch.object(musicbrainz, "http_get_json", fake):
                ok, entry = p._lookup_album("A", "Alb (Deluxe Edition)")
                self.assertEqual((ok, entry), (True, None))  # Live skipped; retried with original
                self.assertEqual(len(calls), 2)
                ok, entry = p._lookup_album("A", "Alb Live")
                self.assertIsNotNone(entry)


if __name__ == "__main__":
    unittest.main()
