import unittest

from bucketer.jev import FALLBACK_BUCKET, GENERIC_LEVELS, build_questions
from bucketer.pipeline import group_key


class GroupKeyTest(unittest.TestCase):
    def test_tracks_of_one_album_share_a_key(self):
        self.assertEqual(group_key("Kyuss", "Wretch"), group_key("Kyuss; Guest", "Wretch (Deluxe Edition)"))

    def test_different_albums_differ(self):
        self.assertNotEqual(group_key("Kyuss", "Wretch"), group_key("Kyuss", "Blues for the Red Sun"))

    def test_unknown_albums_group_per_artist(self):
        self.assertEqual(group_key("Kyuss", "Unknown"), group_key("Kyuss", ""))
        self.assertNotEqual(group_key("Kyuss", ""), group_key("Sleep", ""))


class BuildQuestionsTest(unittest.TestCase):
    def test_other_is_not_a_question_and_defaults_apply(self):
        q = build_questions({"punk": {"description": "Fast punk."}, "other": {"description": "Rest."}})
        self.assertEqual(list(q), ["punk"])
        self.assertEqual(q["punk"].type, "score")
        self.assertEqual(list(q["punk"].criteria), GENERIC_LEVELS)
        self.assertIn("album described in `state`", q["punk"].instructions)
        self.assertIn("Fast punk.", q["punk"].instructions)

    def test_fallback_bucket_in_buckets_json_is_never_asked(self):
        q = build_questions({"punk": {"description": "p"}, FALLBACK_BUCKET: {"description": "x"}})
        self.assertNotIn(FALLBACK_BUCKET, q)

    def test_custom_levels_and_not_for(self):
        levels = [{"summary": "No", "signals": []}, {"summary": "Yes", "signals": ["fast"]}]
        q = build_questions({"punk": {"description": "Fast punk.", "levels": levels, "not_for": "pop punk"}})
        self.assertEqual(list(q["punk"].criteria), levels)
        self.assertTrue(q["punk"].instructions.endswith("Not for: pop punk"))


if __name__ == "__main__":
    unittest.main()
