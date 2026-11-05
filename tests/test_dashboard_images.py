import re
import unittest

from bucketer.dashboard import analyze, render
from bucketer.dashboard.render import STATIC, inline_fonts, inline_images
from bucketer.models import Enrichment, Group


class InlineImagesTest(unittest.TestCase):
    def test_url_replaced_with_data_uri(self):
        css = inline_images(":root{--x:url(img/aero_goldfish.webp)}")
        self.assertRegex(css, r"^:root\{--x:url\(data:image/webp;base64,[A-Za-z0-9+/=]+\)\}$")

    def test_other_urls_untouched(self):
        self.assertEqual(inline_images("a{background:url(https://x/y.png)}"), "a{background:url(https://x/y.png)}")

    def test_missing_file_fails_loudly(self):
        with self.assertRaises(FileNotFoundError):
            inline_images("a{background:url(img/nope.webp)}")

    def test_every_referenced_image_exists_and_is_used_once(self):
        css = "".join(path.read_text(encoding="utf-8") for path in [STATIC / "style.css", *sorted((STATIC / "aero").glob("*.css"))])
        names = re.findall(r"url\(img/([\w.-]+)\)", css)
        self.assertEqual(len(names), len(set(names)))  # each image inlined once, not per selector
        for name in names:
            self.assertTrue((STATIC / "img" / name).is_file(), name)

    def test_font_url_replaced_with_data_uri(self):
        css = inline_fonts("@font-face{src:url(fonts/open-sans-latin-400-normal.woff2) format('woff2')}")
        self.assertRegex(css, r"url\(data:font/woff2;base64,[A-Za-z0-9+/=]+\)")

    def test_render_inlines_fonts(self):
        pair = (Group(key="a|b", artist="a", album="b", release_date="", rows=[0]), Enrichment(album_tags=[{"name": "rock", "count": 100}]))
        self.assertNotIn("url(fonts/", render(analyze([pair]), {}))

    def test_credits_cover_every_photo(self):
        credits = (STATIC / "img" / "CREDITS.md").read_text(encoding="utf-8")
        for path in (STATIC / "img").glob("*.webp"):
            self.assertIn(path.name, credits)

    def test_render_has_no_external_image_references(self):
        pair = (Group(key="a|b", artist="a", album="b", release_date="", rows=[0]), Enrichment(album_tags=[{"name": "rock", "count": 100}]))
        html = render(analyze([pair]), {})
        self.assertNotIn("url(img/", html)
        self.assertIn("data:image/webp;base64,", html)


if __name__ == "__main__":
    unittest.main()


class LaneAssemblyTest(unittest.TestCase):
    def test_render_leaves_no_placeholders(self):
        html = render(analyze([]), {})
        self.assertNotIn("<!--SCENE:", html)
        self.assertNotIn("url(img/", html)
