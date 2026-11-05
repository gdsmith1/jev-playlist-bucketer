import os
import tempfile
import unittest

from bucketer import cli


class DemoTest(unittest.TestCase):
    def test_demo_writes_dashboard_without_csv_or_network(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            self.addCleanup(os.chdir, cwd)
            cli.main(["--demo"])
            runs = os.listdir("runs")
            self.assertEqual(len(runs), 1)
            with open(os.path.join("runs", runs[0], "dashboard.html"), encoding="utf-8") as f:
                html = f.read()
        self.assertIn("Genre Dashboard", html)
        self.assertIn('"jev"', html)

    def test_csv_required_without_demo(self):
        with self.assertRaises(SystemExit):
            cli.main([])


if __name__ == "__main__":
    unittest.main()
