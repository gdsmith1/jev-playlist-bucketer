import os
import tempfile
import unittest
from unittest import mock

import requests

from enrichment import (
    JsonCache,
    Throttle,
    artist_candidates,
    clean_album,
    is_unknown_album,
    clean_tags,
    coverage_stats,
    empty_enrichment,
    format_for_jev,
    format_run_stats,
    http_get_json,
    primary_artist,
)



def tag(name, count=0):
    return {"name": name, "count": count}


class CleanTagsTest(unittest.TestCase):
    def test_lowercases_strips_and_sorts_by_count_then_name(self):
        out = clean_tags([tag(" Stoner Rock ", 100), tag("Hard Rock", 12), tag("desert rock", 12)])
        self.assertEqual([t["name"] for t in out], ["stoner rock", "desert rock", "hard rock"])

    def test_drops_years_decades_and_noise(self):
        out = clean_tags([tag("1991", 47), tag("90s", 30), tag("1990s", 5), tag("seen live", 9),
                          tag("Male Vocalists", 8), tag("grunge", 1)])
        self.assertEqual([t["name"] for t in out], ["grunge"])

    def test_dedupes_keeping_best_count_and_truncates(self):
        out = clean_tags([tag("grunge", 1), tag("Grunge", 50)] + [tag(f"t{i}", 10) for i in range(20)], max_n=3)
        self.assertEqual(out[0], {"name": "grunge", "count": 50})
        self.assertEqual(len(out), 3)

    def test_drops_junk_and_merges_spelling_variants(self):
        out = clean_tags([tag("reissue", 90), tag("wrong track streaming", 80), tag("Synth-pop", 60),
                          tag("synthpop", 40), tag("synth pop", 40), tag("new wave", 20)])
        self.assertEqual([t["name"] for t in out], ["synth-pop", "new wave"])

    def test_vague_tags_rank_below_specific_ones(self):
        out = clean_tags([tag("rock", 100), tag("alternative", 90), tag("post-hardcore", 5)])
        self.assertEqual([t["name"] for t in out], ["post-hardcore", "rock", "alternative"])

    def test_drops_list_membership_and_chatter_tags(self):
        junk = ["1001 albums you must hear before you die", "top metal albums of the decade 2020 - 2029",
                "best of 2013", "allboutguitarcom", "reissue"]
        self.assertEqual(clean_tags([tag(n, 50) for n in junk] + [tag("doom metal", 5)]), [tag("doom metal", 5)])

    def test_keeps_nationality_tags(self):
        out = clean_tags([tag("swedish", 50), tag("death metal", 40)])
        self.assertEqual([t["name"] for t in out], ["swedish", "death metal"])

    def test_drops_echoes_of_excluded_names(self):
        out = clean_tags([tag("Quicksand", 100), tag("manic compression", 50), tag("post-hardcore", 5)],
                         exclude=("Quicksand", "Manic Compression"))
        self.assertEqual([t["name"] for t in out], ["post-hardcore"])

    def test_accepts_none_and_bare_strings(self):
        self.assertEqual(clean_tags(None), [])
        self.assertEqual(clean_tags(["Metal"]), [{"name": "metal", "count": 0}])


class NameCleaningTest(unittest.TestCase):
    def test_primary_artist(self):
        self.assertEqual(primary_artist("Filter; The Crystal Method"), "Filter")
        self.assertEqual(primary_artist("A feat. B"), "A")
        self.assertEqual(primary_artist("A ft. B"), "A")
        self.assertEqual(primary_artist("Simon & Garfunkel"), "Simon")
        self.assertEqual(primary_artist("Kyuss"), "Kyuss")

    def test_artist_candidates_keep_full_string_second(self):
        self.assertEqual(artist_candidates("Simon & Garfunkel"), ["Simon", "Simon & Garfunkel"])
        self.assertEqual(artist_candidates("Kyuss"), ["Kyuss"])

    def test_clean_album(self):
        self.assertEqual(clean_album("Wretch (Deluxe Edition)"), "Wretch")
        self.assertEqual(clean_album("Wretch (Remastered 2009)"), "Wretch")
        self.assertEqual(clean_album("Wretch - Expanded Edition"), "Wretch")
        self.assertEqual(clean_album("Wretch [Bonus Tracks]"), "Wretch")
        self.assertEqual(clean_album("The End Complete (Reissue)"), "The End Complete")
        self.assertEqual(clean_album("Wretch"), "Wretch")


class FormatForJevTest(unittest.TestCase):
    @staticmethod
    def enrichment(album=None, artist=None, similar=None):
        e = empty_enrichment("lastfm")
        e["levels"]["album"] = {"genres": [], "tags": album} if album is not None else None
        e["levels"]["artist"] = {"genres": [], "tags": artist} if artist is not None else None
        if similar:
            e["extras"]["similar_artists"] = similar
        return e

    def test_no_data_is_just_the_head(self):
        text = format_for_jev("Kyuss", "Wretch", "1991-01-01", empty_enrichment("lastfm"))
        self.assertEqual(text, "Album: Wretch by Kyuss (1991)")

    def test_album_artist_and_similar_sections_without_numbers(self):
        e = self.enrichment(album=[tag("stoner rock", 100), tag("stoner metal", 86)],
                            artist=[tag("desert rock", 8)], similar=["Fu Manchu", "Sleep"])
        text = format_for_jev("Kyuss; Someone", "Wretch (Deluxe Edition)", "1991", e)
        self.assertEqual(
            text,
            "Album: Wretch by Kyuss (1991)\n"
            "Album tags (strongest first): stoner rock, stoner metal\n"
            "Artist tags (strongest first): desert rock\n"
            "Similar artists: Fu Manchu, Sleep",
        )

    def test_artist_tags_already_shown_at_album_level_are_omitted(self):
        e = self.enrichment(album=[tag("rock", 5), tag("grunge", 9)], artist=[tag("rock", 5)])
        text = format_for_jev("A", "B", "", e)
        self.assertNotIn("Artist tags", text)
        self.assertEqual(text.splitlines()[0], "Album: B by A")

    def test_unknown_album_describes_the_artist_only(self):
        e = self.enrichment(artist=[tag("grunge", 9)])
        text = format_for_jev("Kyuss", "Unknown", "1991", e)
        self.assertEqual(text, "Artist: Kyuss\nArtist tags (strongest first): grunge")

    def test_caps_items_per_level(self):
        e = self.enrichment(artist=[tag(f"t{i}", 100 - i) for i in range(10)])
        text = format_for_jev("A", "B", "1990", e)
        self.assertIn("t5", text)
        self.assertNotIn("t6", text)

    def test_deterministic_regardless_of_input_order(self):
        a = self.enrichment(artist=[tag("b", 5), tag("a", 5), tag("c", 9)])
        b = self.enrichment(artist=[tag("c", 9), tag("a", 5), tag("b", 5)])
        self.assertEqual(format_for_jev("X", "Y", "1990", a), format_for_jev("X", "Y", "1990", b))

    def test_length_cap_drops_similar_artists_first(self):
        e = self.enrichment(artist=[tag("rock", 1)], similar=["x" * 200] * 5)
        text = format_for_jev("A", "B", "1990", e)
        self.assertLessEqual(len(text), 600)
        self.assertIn("Artist tags (strongest first): rock", text)


class UnknownAlbumTest(unittest.TestCase):
    def test_values(self):
        self.assertTrue(is_unknown_album(" Unknown Album "))
        self.assertTrue(is_unknown_album(""))
        self.assertFalse(is_unknown_album("Wretch"))


class CoverageStatsTest(unittest.TestCase):
    def test_counts(self):
        full = empty_enrichment("x")
        full["levels"]["album"] = {"genres": ["rock"], "tags": []}
        full["levels"]["artist"] = {"genres": [], "tags": [tag("metal", 1)]}
        empty_level = empty_enrichment("x")
        empty_level["levels"]["album"] = {"genres": [], "tags": []}
        stats = coverage_stats([full, empty_level, empty_enrichment("x")])
        self.assertEqual(stats, {"albums": 3, "album": 1, "artist": 1, "any": 1, "none": 2})

    def test_run_stats_text(self):
        stats = coverage_stats([empty_enrichment("x")])
        text = format_run_stats("x", stats, {"calls": 3, "cache_hits": 1, "errors": 0}, 12.4)
        self.assertEqual(
            text,
            "x coverage over 1 albums: album 0/1  artist 0/1  any 0/1  none 1/1\n"
            "x calls: 3  cache_hits: 1  errors: 0   elapsed: 12s",
        )


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


class JsonCacheTest(unittest.TestCase):
    def test_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            cache = JsonCache(path)
            self.assertEqual(cache.data, {})
            cache.section("artist")["kyuss"] = None
            cache.set("x", 1)
            cache.flush()
            again = JsonCache(path)
            self.assertIn("kyuss", again.section("artist"))
            self.assertEqual(again.get("x"), 1)
            self.assertIsNone(again.get("missing"))


def response(status, body=None, headers=None):
    resp = mock.Mock()
    resp.status_code = status
    resp.headers = headers or {}
    if body is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body
    return resp


class HttpGetJsonTest(unittest.TestCase):
    def test_retries_503_then_succeeds(self):
        client = mock.Mock()
        client.get.side_effect = [response(503, {}), response(503, {}), response(200, {"ok": 1})]
        sleeps = []
        status, data = http_get_json(client, "u", sleep=sleeps.append)
        self.assertEqual((status, data), (200, {"ok": 1}))
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_honors_retry_after(self):
        client = mock.Mock()
        client.get.side_effect = [response(429, {}, {"Retry-After": "7"}), response(200, {})]
        sleeps = []
        http_get_json(client, "u", sleep=sleeps.append)
        self.assertEqual(sleeps, [7.0])

    def test_gives_up_after_max_retries(self):
        client = mock.Mock()
        client.get.return_value = response(503, {})
        sleeps = []
        status, data = http_get_json(client, "u", max_retries=2, sleep=sleeps.append)
        self.assertEqual((status, data), (503, None))
        self.assertEqual(client.get.call_count, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_404_is_not_retried(self):
        client = mock.Mock()
        client.get.return_value = response(404, {"error": "nope"})
        self.assertEqual(http_get_json(client, "u", sleep=lambda s: None), (404, {"error": "nope"}))
        self.assertEqual(client.get.call_count, 1)

    def test_timeouts_retry_and_never_raise(self):
        client = mock.Mock()
        client.get.side_effect = requests.Timeout("slow")
        self.assertEqual(http_get_json(client, "u", max_retries=1, sleep=lambda s: None), (0, None))
        self.assertEqual(client.get.call_count, 2)

    def test_non_json_body(self):
        client = mock.Mock()
        client.get.return_value = response(200, None)
        self.assertEqual(http_get_json(client, "u"), (200, None))

    def test_throttle_called_per_attempt(self):
        client = mock.Mock()
        client.get.side_effect = [response(503, {}), response(200, {})]
        throttle = mock.Mock()
        http_get_json(client, "u", throttle=throttle, sleep=lambda s: None)
        self.assertEqual(throttle.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
