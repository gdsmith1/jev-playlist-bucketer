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
    clean_tags,
    clean_track,
    coverage_stats,
    empty_enrichment,
    format_for_jev,
    format_run_stats,
    http_get_json,
    primary_artist,
)

FIELDS = ["Kyuss", "Hwy 74", "Wretch", "1991", "00:04:43", "USEE10181126"]


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
        out = clean_tags([tag("rock", 1), tag("Rock", 50)] + [tag(f"t{i}", 10) for i in range(20)], max_n=3)
        self.assertEqual(out[0], {"name": "rock", "count": 50})
        self.assertEqual(len(out), 3)

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

    def test_clean_track(self):
        self.assertEqual(clean_track("Song - Remastered 2009"), "Song")
        self.assertEqual(clean_track("Song (Remastered)"), "Song")
        self.assertEqual(clean_track("Song (Live at Wembley)"), "Song")
        self.assertEqual(clean_track("Song [Bonus]"), "Song")
        self.assertEqual(clean_track("Song (feat. Other)"), "Song")
        self.assertEqual(clean_track("Song - 2011 Remaster"), "Song")

    def test_clean_track_keeps_leading_parenthetical_and_never_returns_empty(self):
        self.assertEqual(clean_track("(Do Not Feed The) Oyster"), "(Do Not Feed The) Oyster")
        self.assertEqual(clean_track("[Intro]"), "[Intro]")

    def test_clean_album(self):
        self.assertEqual(clean_album("Wretch (Deluxe Edition)"), "Wretch")
        self.assertEqual(clean_album("Wretch (Remastered 2009)"), "Wretch")
        self.assertEqual(clean_album("Wretch - Expanded Edition"), "Wretch")
        self.assertEqual(clean_album("Wretch [Bonus Tracks]"), "Wretch")
        self.assertEqual(clean_album("Wretch"), "Wretch")


class FormatForJevTest(unittest.TestCase):
    def test_all_none(self):
        text = format_for_jev(FIELDS, empty_enrichment("lastfm"))
        self.assertEqual(
            text,
            "Kyuss, Hwy 74, Wretch, 1991, 00:04:43 | track: no data | album: no data | artist: no data",
        )

    def test_mixed_levels_dedupe_and_annotation(self):
        enrichment = empty_enrichment("lastfm")
        enrichment["levels"]["album"] = {"genres": [], "tags": [tag("stoner rock", 100), tag("stoner metal", 86)]}
        enrichment["levels"]["artist"] = {"genres": ["stoner rock"], "tags": [tag("desert rock", 8)]}
        text = format_for_jev(FIELDS, enrichment)
        self.assertIn("track: no data", text)
        self.assertIn("album: stoner rock (x2), stoner metal", text)
        self.assertIn("artist: desert rock", text)

    def test_level_fully_covered_by_higher_level(self):
        enrichment = empty_enrichment("x")
        enrichment["levels"]["album"] = {"genres": ["rock"], "tags": []}
        enrichment["levels"]["artist"] = {"genres": ["rock"], "tags": []}
        self.assertIn("artist: same as higher level", format_for_jev(FIELDS, enrichment))

    def test_caps_items_per_level(self):
        enrichment = empty_enrichment("x")
        enrichment["levels"]["artist"] = {"genres": [], "tags": [tag(f"t{i}", 100 - i) for i in range(10)]}
        text = format_for_jev(FIELDS, enrichment)
        self.assertIn("t5", text)
        self.assertNotIn("t6", text)

    def test_info_section(self):
        enrichment = empty_enrichment("x")
        enrichment["extras"] = {"artist_type": "Group", "artist_country": "US", "artist_begin": "1987",
                                "have": 12603}
        text = format_for_jev(FIELDS, enrichment)
        self.assertTrue(text.endswith("| info: group from US; began 1987; 12603 collectors"))

    def test_deterministic_regardless_of_input_order(self):
        a, b = empty_enrichment("x"), empty_enrichment("x")
        a["levels"]["artist"] = {"genres": [], "tags": [tag("b", 5), tag("a", 5), tag("c", 9)]}
        b["levels"]["artist"] = {"genres": [], "tags": [tag("c", 9), tag("a", 5), tag("b", 5)]}
        self.assertEqual(format_for_jev(FIELDS, a), format_for_jev(FIELDS, b))

    def test_length_cap_truncates_info_first(self):
        enrichment = empty_enrichment("x")
        enrichment["levels"]["artist"] = {"genres": ["rock"], "tags": []}
        enrichment["extras"] = {"similar_artists": ["x" * 200] * 5, "artist_listeners": 5}
        text = format_for_jev(FIELDS, enrichment)
        self.assertLessEqual(len(text), 600)
        self.assertIn("artist: rock", text)


class CoverageStatsTest(unittest.TestCase):
    def test_counts(self):
        full = empty_enrichment("x")
        full["levels"]["album"] = {"genres": ["rock"], "tags": []}
        full["levels"]["artist"] = {"genres": [], "tags": [tag("metal", 1)]}
        empty_level = empty_enrichment("x")
        empty_level["levels"]["track"] = {"genres": [], "tags": []}
        stats = coverage_stats([full, empty_level, empty_enrichment("x")])
        self.assertEqual(stats, {"songs": 3, "track": 0, "album": 1, "artist": 1, "any": 1, "none": 2})

    def test_run_stats_text(self):
        stats = coverage_stats([empty_enrichment("x")])
        text = format_run_stats("x", stats, {"calls": 3, "cache_hits": 1, "errors": 0}, 12.4)
        self.assertEqual(
            text,
            "x level coverage over 1 songs: track 0/1  album 0/1  artist 0/1  any 0/1  none 1/1\n"
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
