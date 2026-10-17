import unittest

from bucketer.formatting import coverage_stats, format_for_jev, format_run_stats
from bucketer.models import Enrichment


def tag(name, count=0):
    return {"name": name, "count": count}

class FormatForJevTest(unittest.TestCase):
    @staticmethod
    def enrichment(album=None, artist=None, similar=None):
        return Enrichment(album_tags=album, artist_tags=artist, similar_artists=similar or [])

    def test_no_data_is_just_the_head(self):
        text = format_for_jev("Kyuss", "Wretch", "1991-01-01", Enrichment())
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


class CoverageStatsTest(unittest.TestCase):
    def test_counts(self):
        full = Enrichment(album_tags=[tag("rock", 1)], artist_tags=[tag("metal", 1)])
        empty_level = Enrichment(album_tags=[])
        stats = coverage_stats([full, empty_level, Enrichment()])
        self.assertEqual(stats, {"albums": 3, "album": 1, "artist": 1, "any": 1, "none": 2})

    def test_run_stats_text(self):
        stats = coverage_stats([Enrichment()])
        text = format_run_stats(stats, {"calls": 3, "cache_hits": 1, "errors": 0}, 12.4)
        self.assertEqual(
            text,
            "lastfm coverage over 1 albums: album 0/1  artist 0/1  any 0/1  none 1/1\n"
            "lastfm calls: 3  cache_hits: 1  errors: 0   elapsed: 12s",
        )


if __name__ == "__main__":
    unittest.main()
