import unittest

from bucketer.dashboard.analysis import analyze
from bucketer.dashboard.render import render


class WeightTest(unittest.TestCase):
    def test_empty_dashboard_under_6mb(self):
        html = render(analyze([]), {})
        self.assertLess(len(html.encode("utf-8")), 6 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
