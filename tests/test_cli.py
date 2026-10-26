import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from bucketer import cli
from bucketer.dashboard import analysis as analysis_module
from bucketer.models import Enrichment

HEADER = "Artist(s) Name , Track Name , Album Name , Release Date , Length , ISRC"
ROWS = ["Kyuss , Green Machine , Wretch , 1991 , 3:00 , X", "Kyuss , Demon Cleaner , Wretch (Deluxe Edition) , 1991 , 3:00 , X",
        "Sleep , Dopesmoker , Dopesmoker , 2003 , 3:00 , X"]


def write_custom():
    with open("custom.json", "w") as f:
        f.write('{"mine": {"description": "Mine"}}')


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        for name in ("MIN_CLUSTER_ALBUMS", "MIN_CLUSTER_SONGS", "MIN_TAG_ALBUMS"):
            patcher = mock.patch.object(analysis_module, name, 1)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, *extra, scores=None, select="all", yes=True, prep=None):
        extra = (*(("--select", select) if select else ()), *(("--yes",) if yes else ()), *extra)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, cwd)
        with open("p.csv", "w") as f:
            f.write("\n".join([HEADER, *ROWS]) + "\n")
        if prep:
            prep()
        self.lastfm = fake_lastfm = mock.Mock(stats={"calls": 0, "cache_hits": 0, "errors": 0})
        fake_lastfm.fetch.return_value = Enrichment(artist_tags=[{"name": "stoner rock", "count": 100}])
        fake_lastfm.tag_info.return_value = {"summary": "Heavy.", "reach": 5, "taggings": 9}
        fake_jev = mock.Mock(usage={"input_tokens": 0, "output_tokens": 0, "call_count": 0})
        fake_jev.is_cached.return_value = False
        fake_jev.score.side_effect = lambda text, label: (scores or {})[label]
        with mock.patch.object(cli, "load_dotenv"), mock.patch.object(cli, "LastfmClient", return_value=fake_lastfm), \
                mock.patch.object(cli, "JevClient", return_value=fake_jev) as self.jev_cls, contextlib.redirect_stdout(io.StringIO()):
            cli.main(["p.csv", *extra])
        return fake_jev, os.path.join("runs", os.listdir("runs")[0])

    def read(self, run_dir, name):
        with open(os.path.join(run_dir, name)) as f:
            return f.read().splitlines()

    def test_real_run_writes_buckets_one_jev_call_per_album(self):
        jev, run_dir = self.run_main(scores={"kyuss|wretch": {"stoner_rock": 2}, "sleep|dopesmoker": {"stoner_rock": 0}})
        self.assertEqual(jev.score.call_count, 2)
        self.assertEqual(sorted(os.listdir(run_dir)), ["dashboard.html", "other.csv", "recommended_buckets.json", "selected_buckets.json", "stoner_rock.csv"])
        self.assertEqual(self.read(run_dir, "stoner_rock.csv"), [HEADER, *ROWS[:2]])
        self.assertEqual(self.read(run_dir, "other.csv"), [HEADER, ROWS[2]])

    def test_dry_run_never_scores_and_writes_nothing(self):
        jev, run_dir = self.run_main("--dry-run")
        jev.score.assert_not_called()
        self.assertEqual(sorted(os.listdir(run_dir)), ["dashboard.html", "recommended_buckets.json"])

    def test_dry_run_never_builds_jev_client(self):
        with mock.patch.object(cli, "JevClient") as jev_cls:
            self.run_main("--dry-run", "--no-dashboard")
        jev_cls.assert_not_called()

    def test_all_albums_fetched_before_selection_and_scoring(self):
        seen = {}
        def fake_choose(suggested, select, buckets_path=None, run_dir=None):
            seen["fetched"] = fake_lastfm_calls()
            seen["suggested"] = list(suggested)
            return {"stoner_rock": {"description": "d", "source": "recommended"}}
        fake_lastfm_calls = lambda: self.lastfm.fetch.call_count
        with mock.patch.object(cli, "choose_buckets", side_effect=fake_choose):
            self.run_main(scores={"kyuss|wretch": {"stoner_rock": 0}, "sleep|dopesmoker": {"stoner_rock": 0}})
        self.assertEqual(seen, {"fetched": 2, "suggested": ["stoner_rock"]})

    def test_dry_run_no_dashboard_writes_nothing(self):
        jev, run_dir = self.run_main("--dry-run", "--no-dashboard")
        jev.score.assert_not_called()
        self.assertEqual(os.listdir(run_dir), ["recommended_buckets.json"])
        with open(os.path.join(run_dir, "recommended_buckets.json")) as f:
            self.assertEqual(list(json.load(f)), ["stoner_rock"])

    def test_real_run_writes_dashboard_and_selected_buckets_before_scoring(self):
        _, run_dir = self.run_main(scores={"kyuss|wretch": {"stoner_rock": 0}, "sleep|dopesmoker": {"stoner_rock": 0}})
        self.assertIn("dashboard.html", os.listdir(run_dir))
        with open(os.path.join(run_dir, "selected_buckets.json")) as f:
            self.assertEqual(list(json.load(f)), ["stoner_rock"])

    def test_select_none_with_custom_buckets_file_and_jev_result(self):
        scores = {"kyuss|wretch": {"mine": 2}, "sleep|dopesmoker": {"mine": 0}}
        with mock.patch.object(cli, "write_dashboard", return_value="d.html") as wd:
            _jev, run_dir = self.run_main("--buckets", "custom.json", scores=scores, select="none", prep=write_custom)
        with open(os.path.join(run_dir, "selected_buckets.json")) as f:
            self.assertEqual(json.load(f), {"mine": {"description": "Mine", "source": "custom"}})
        self.assertEqual(self.jev_cls.call_args.args[0], {"mine": {"description": "Mine", "source": "custom"}})
        self.assertEqual(wd.call_count, 2)
        self.assertNotIn("jev_result", wd.call_args_list[0].kwargs)
        self.assertEqual(wd.call_args.kwargs["jev_result"], {
            "threshold": 0.8, "buckets": {"mine": {"description": "Mine", "source": "custom"}},
            "albums": [{"scores": {"mine": 2}, "matched": ["mine"]}, {"scores": {"mine": 0}, "matched": []}]})

    def test_real_run_no_dashboard_flag(self):
        _, run_dir = self.run_main("--no-dashboard", scores={"kyuss|wretch": {"stoner_rock": 0}, "sleep|dopesmoker": {"stoner_rock": 0}})
        self.assertNotIn("dashboard.html", os.listdir(run_dir))

    def test_real_run_declined_at_confirmation_never_scores(self):
        with mock.patch("bucketer.checkpoint.interactive", return_value=True), mock.patch("bucketer.checkpoint.ask_confirm", return_value=False), \
                self.assertRaises(SystemExit):
            self.run_main(yes=False)
        self.jev_cls.return_value.score.assert_not_called()

    def test_real_run_without_yes_and_without_terminal_never_scores(self):
        with mock.patch("bucketer.checkpoint.interactive", return_value=False), self.assertRaisesRegex(SystemExit, "--yes"):
            self.run_main(yes=False)
        self.jev_cls.return_value.score.assert_not_called()

    def test_real_run_without_terminal_or_select_exits_before_jev(self):
        with mock.patch("bucketer.checkpoint.interactive", return_value=False), self.assertRaises(SystemExit):
            self.run_main(select=None)
        self.jev_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
