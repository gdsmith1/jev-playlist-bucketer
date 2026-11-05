"""Assembles dashboard.html from the static page, stylesheet and section scripts, with the analysis embedded as JSON."""

import base64
import json
import os
import re
from collections.abc import Callable
from pathlib import Path

from ..models import Enrichment, Group
from .analysis import analyze

STATIC = Path(__file__).parent / "static"
LANES = ["sky", "hero", "bubbles", "water", "animals", "ui", "polish", "v3"]  # stylesheet order after style.css; ui holds all page chrome
SCENE_LANES = ["sky", "hero", "water", "animals", "bubbles", "v3"]  # each has aero/<lane>.html injected at <!--SCENE:<lane>-->
SECTIONS = ["stats", "clusters", "coverage", "tags", "heatmap", "outliers", "drilldown", "quality", "noise", "decades", "similar", "selected", "playlist", "tabs", "fx"]  # page order; each file draws one section


def _read(relative: str) -> str:
    return (STATIC / relative).read_text(encoding="utf-8")


IMG_URL = re.compile(r"url\(img/([A-Za-z0-9_.-]+)\)")
IMG_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def inline_images(css: str) -> str:
    """Replace each `url(img/<file>)` with a base64 data URI so the dashboard stays a single self-contained file."""
    def embed(match: re.Match) -> str:
        path = STATIC / "img" / match.group(1)
        mime = IMG_TYPES[path.suffix.lower()]
        return f"url(data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')})"
    return IMG_URL.sub(embed, css)


FONT_URL = re.compile(r"url\(fonts/([A-Za-z0-9_.-]+\.woff2)\)")


def inline_fonts(css: str) -> str:
    """Replace each `url(fonts/<file>.woff2)` with a base64 data URI (bundled Open Sans), keeping the report one file."""
    def embed(match: re.Match) -> str:
        data = base64.b64encode((STATIC / "fonts" / match.group(1)).read_bytes()).decode("ascii")
        return f"url(data:font/woff2;base64,{data})"
    return FONT_URL.sub(embed, css)


def render(analysis: dict, tag_info: dict[str, dict]) -> str:
    data = json.dumps({**analysis, "info": tag_info}, ensure_ascii=False).replace("</", "<\\/")
    script = "\n".join([_read("app.js")] + [_read(f"sections/{name}.js") for name in SECTIONS])
    css = "\n".join([_read("style.css")] + [_read(f"aero/{name}.css") for name in LANES])
    page = _read("page.html").replace("/*CSS*/", inline_fonts(inline_images(css))).replace("/*JS*/", script)
    for name in SCENE_LANES:
        page = page.replace(f"<!--SCENE:{name}-->", _read(f"aero/{name}.html"))
    return page.replace("/*DATA*/null", data)


def write_dashboard(run_dir: str, pairs: list[tuple[Group, Enrichment]], tag_info: Callable[[str], dict | None], jev_result: dict | None = None, songs: list[dict] | None = None) -> str:
    analysis = analyze(pairs, jev_result, songs)
    info = {}
    for row in analysis["tags"]:
        found = tag_info(row["tag"])
        if found and found.get("summary"):
            info[row["tag"]] = {"summary": found["summary"], "reach": found.get("reach", 0)}
    path = os.path.join(run_dir, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(analysis, info))
    return path
