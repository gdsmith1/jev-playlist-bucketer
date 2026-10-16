import unittest

from bucketer.names import artist_candidates, clean_album, is_unknown_album, primary_artist

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


class UnknownAlbumTest(unittest.TestCase):
    def test_values(self):
        self.assertTrue(is_unknown_album(" Unknown Album "))
        self.assertTrue(is_unknown_album(""))
        self.assertFalse(is_unknown_album("Wretch"))



if __name__ == "__main__":
    unittest.main()
