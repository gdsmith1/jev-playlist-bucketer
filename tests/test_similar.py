import unittest

from bucketer.dashboard import analyze
from bucketer.dashboard.similar import similar_to_outliers
from bucketer.models import Enrichment, Group


def pair(artist, tags, similar=(), songs=1):
    group = Group(key=artist, artist=artist, album="x", release_date="", rows=list(range(songs)))
    return group, Enrichment(artist_tags=[{"name": n, "count": c} for n, c in tags], similar_full=[{"name": n, "match": m} for n, m in similar])


class SimilarNetworkTest(unittest.TestCase):
    def test_rows_split_neighbours_and_lean_towards_their_bucket(self):
        albums = [
            {"artist": "Odd", "similar_full": [{"name": "Kyuss", "match": 0.9}, {"name": "Missing", "match": 0.8}, {"name": "Weak", "match": 0.05}]},
            {"artist": "Kyuss", "similar_full": []},
        ]
        records = [{"artist": "Kyuss", "best_cluster": "stoner", "songs": 3}, {"artist": "Odd", "best_cluster": None, "songs": 1}]
        out = similar_to_outliers(albums, records, [{"artist": "Odd"}])
        self.assertEqual(out["rows"], [{"artist": "Odd", "inside": ["Kyuss"], "outside": ["Missing"], "leans": "stoner"}])
        self.assertEqual(out["recommended"], [{"artist": "Missing", "score": 0.8}])
        self.assertEqual((out["with_neighbours"], out["outliers"]), (1, 1))

    def test_outlier_without_similar_data_has_no_row(self):
        out = similar_to_outliers([{"artist": "Odd", "similar_full": []}], [], [{"artist": "Odd"}])
        self.assertEqual((out["rows"], out["with_neighbours"], out["recommended"]), ([], 0, []))

    def test_analyze_includes_network(self):
        pairs = [pair("A", [("x", 100)]), pair("B", [("x", 100)]), pair("Odd", [], similar=[("A", 0.7), ("Ghost", 0.6)])]
        net = analyze(pairs)["similar_network"]
        self.assertEqual(net["rows"][0]["artist"], "Odd")
        self.assertEqual(net["rows"][0]["inside"], ["A"])
        self.assertEqual(net["rows"][0]["outside"], ["Ghost"])
