import os
import tempfile
import unittest

from bucketer.cache import JsonCache

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

    def test_fresh_ignores_existing_file_and_overwrites_on_flush(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            old = JsonCache(path)
            old.set("x", 1)
            old.flush()
            fresh = JsonCache(path, fresh=True)
            self.assertEqual(fresh.data, {})
            fresh.set("y", 2)
            fresh.flush()
            again = JsonCache(path)
            self.assertIsNone(again.get("x"))
            self.assertEqual(again.get("y"), 2)



if __name__ == "__main__":
    unittest.main()
