import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from bucketer import checkpoint

CLUSTERS = [
    {"seed": "stoner rock", "tags": ["stoner rock", "desert rock", "fuzz"], "examples": ["Kyuss", "Sleep"], "albums": 4, "songs": 9},
    {"seed": "Post-Punk!", "tags": ["post-punk"], "examples": [], "albums": 2, "songs": 3},
]


class SuggestTest(unittest.TestCase):
    def test_keys_and_fixed_template_descriptions(self):
        suggested = checkpoint.suggest_buckets(CLUSTERS)
        self.assertEqual(list(suggested), ["stoner_rock", "post_punk"])
        self.assertEqual(suggested["stoner_rock"]["description"], "Albums tagged stoner rock, desert rock, fuzz, in the vein of Kyuss, Sleep.")
        self.assertEqual(suggested["post_punk"]["description"], "Albums tagged post-punk.")

    def test_keys_never_collide_or_use_the_fallback_name(self):
        clusters = [{"seed": "other", "tags": ["other"], "albums": 1, "songs": 1}, {"seed": "Punk", "tags": ["a"], "albums": 1, "songs": 1},
                    {"seed": "punk", "tags": ["b"], "albums": 1, "songs": 1}]
        self.assertEqual(list(checkpoint.suggest_buckets(clusters)), ["other_genre", "punk", "punk_2"])


class ChooseTest(unittest.TestCase):
    def setUp(self):
        self.suggested = checkpoint.suggest_buckets(CLUSTERS)

    def test_select_all_and_list(self):
        self.assertEqual(list(checkpoint.choose_buckets(self.suggested, "all")), ["stoner_rock", "post_punk"])
        chosen = checkpoint.choose_buckets(self.suggested, "post_punk")
        self.assertEqual(chosen, {"post_punk": {"description": "Albums tagged post-punk."}})

    def test_unknown_name_exits(self):
        with self.assertRaisesRegex(SystemExit, "unknown bucket"):
            checkpoint.choose_buckets(self.suggested, "nope")

    def test_no_terminal_and_no_select_exits(self):
        with mock.patch.object(checkpoint, "interactive", return_value=False), mock.patch.object(checkpoint, "ask_checkbox") as ask:
            with self.assertRaisesRegex(SystemExit, "--select"):
                checkpoint.choose_buckets(self.suggested, None)
        ask.assert_not_called()

    def test_prompt_choice_is_used(self):
        with mock.patch.object(checkpoint, "interactive", return_value=True), mock.patch.object(checkpoint, "ask_checkbox", return_value=["stoner_rock"]) as ask:
            chosen = checkpoint.choose_buckets(self.suggested, None)
        self.assertEqual(list(chosen), ["stoner_rock"])
        self.assertIn("4 albums, 9 songs", ask.call_args.args[1][0][0])

    def test_ctrl_c_and_empty_selection_exit(self):
        for answer in (None, []):
            with mock.patch.object(checkpoint, "interactive", return_value=True), mock.patch.object(checkpoint, "ask_checkbox", return_value=answer):
                with self.assertRaisesRegex(SystemExit, "Nothing was sent to jev"):
                    checkpoint.choose_buckets(self.suggested, None)

    def test_no_suggestions_exits(self):
        with self.assertRaisesRegex(SystemExit, "No bucket suggestions"):
            checkpoint.choose_buckets({}, "all")

    def test_write_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = checkpoint.write_selected(tmp, {"a": {"description": "d"}})
            self.assertEqual(os.path.basename(path), "selected_buckets.json")
            with open(path) as f:
                self.assertEqual(json.load(f), {"a": {"description": "d"}})


class ConfirmSpendTest(unittest.TestCase):
    def jev(self, cached=()):
        return mock.Mock(is_cached=lambda t: t in cached)

    def run_confirm(self, jev, texts, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            checkpoint.confirm_spend(jev, texts, 2, **kw)
        return out.getvalue()

    def test_counts_uncached_albums_and_shows_sample_before_asking(self):
        with mock.patch.object(checkpoint, "interactive", return_value=True), mock.patch.object(checkpoint, "ask_confirm", return_value=True) as ask:
            out = self.run_confirm(self.jev(cached={"a"}), ["a", "b\nline2", "c"])
        self.assertIn("2 call(s) needed for 3 album(s) (1 cached), each asking 2 bucket question(s)", out)
        self.assertIn("sample input: b\n", out)
        self.assertNotIn("sample input: a", out)
        ask.assert_called_once()

    def test_declined_or_cancelled_exits(self):
        for answer in (False, None):
            with mock.patch.object(checkpoint, "interactive", return_value=True), mock.patch.object(checkpoint, "ask_confirm", return_value=answer):
                with self.assertRaisesRegex(SystemExit, "Nothing was sent to jev"):
                    self.run_confirm(self.jev(), ["a"])

    def test_no_terminal_needs_yes(self):
        with mock.patch.object(checkpoint, "interactive", return_value=False), mock.patch.object(checkpoint, "ask_confirm") as ask:
            with self.assertRaisesRegex(SystemExit, "--yes"):
                self.run_confirm(self.jev(), ["a"])
            self.run_confirm(self.jev(), ["a"], yes=True)
        ask.assert_not_called()

    def test_nothing_to_send_needs_no_confirmation(self):
        with mock.patch.object(checkpoint, "ask_confirm") as ask:
            out = self.run_confirm(self.jev(cached={"a"}), ["a"])
        self.assertIn("0 call(s) needed", out)
        ask.assert_not_called()

    def test_sample_is_limited(self):
        out = self.run_confirm(self.jev(), ["a", "b", "c", "d", "e"], yes=True)
        self.assertEqual(out.count("sample input"), checkpoint.SAMPLE_TEXTS)


if __name__ == "__main__":
    unittest.main()
