import os
import tempfile
import unittest
from unittest import mock

from bucketer.pipeline import assign_to_buckets, group_rows, load_rows, matching_buckets, write_buckets

HEADER = "Artist(s) Name , Track Name , Album Name , Release Date , Length , ISRC"


def row(artist, track, album, date="1991-01-01"):
    return f"{artist} , {track} , {album} , {date} , 3:00 , X"


class PipelineTest(unittest.TestCase):
    def csv(self, *lines):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "p.csv")
        with open(path, "w") as f:
            f.write("\n".join([HEADER, *lines]) + "\n")
        return path

    def test_load_rows_limit_skips_blank_and_malformed(self):
        path = self.csv(row("A", "1", "X"), "", "garbage", row("B", "2", "Y"), row("C", "3", "Z"))
        with mock.patch("sys.stderr"):
            header, lines = load_rows(path, limit=2)
        self.assertEqual(header, HEADER)
        self.assertEqual([l.split(" , ")[0] for l in lines], ["A", "B"])

    def test_sample_is_deterministic_and_keeps_order(self):
        path = self.csv(*[row(f"A{i}", "t", f"X{i}") for i in range(20)])
        first = load_rows(path, limit=0, sample=5, seed=7)[1]
        self.assertEqual(first, load_rows(path, limit=0, sample=5, seed=7)[1])
        self.assertEqual(first, sorted(first, key=lambda l: int(l.split(" , ")[0][1:])))

    def test_group_rows_shares_album_and_keeps_first_fields(self):
        lines = [row("Kyuss", "1", "Wretch", "1991-01-01"), row("Sleep", "2", "Dopesmoker"),
                 row("Kyuss; Guest", "3", "Wretch (Deluxe Edition)", "2011-01-01")]
        groups = group_rows(lines)
        self.assertEqual([g.rows for g in groups], [[0, 2], [1]])
        self.assertEqual((groups[0].artist, groups[0].album, groups[0].release_date), ("Kyuss", "Wretch", "1991-01-01"))

    def test_matching_buckets_threshold_and_fallback(self):
        self.assertEqual(matching_buckets({"a": 1.0, "b": 0.5, "other": 2}, 1.0), ["a"])
        self.assertEqual(matching_buckets({"a": 0.5}, 1.0), ["other"])

    def test_duplicate_lines_each_kept_and_dry_run_lands_nowhere(self):
        lines = ["x", "x", "y"]
        out = assign_to_buckets(lines, {0: ["a"], 1: ["a"], 2: ["other"]}, ["a", "other"])
        self.assertEqual(out, {"a": ["x", "x"], "other": ["y"]})
        self.assertEqual(assign_to_buckets(lines, {}, ["a"]), {"a": [], "other": []})

    def test_write_buckets_skips_empty(self):
        with tempfile.TemporaryDirectory() as d:
            write_buckets(d, HEADER, {"a": ["x"], "other": []})
            self.assertEqual(os.listdir(d), ["a.csv"])
            with open(os.path.join(d, "a.csv")) as f:
                self.assertEqual(f.read(), HEADER + "\nx\n")


if __name__ == "__main__":
    unittest.main()
