"""Assembles dashboard.html from the static page, stylesheet and section scripts, with the analysis embedded as JSON."""

import json
import os
from collections.abc import Callable
from pathlib import Path

from ..models import Enrichment, Group
from .analysis import analyze

STATIC = Path(__file__).parent / "static"
SECTIONS = ["stats", "clusters", "coverage", "tags", "heatmap", "outliers", "drilldown", "quality", "noise", "decades", "similar", "selected", "playlist", "tabs"]  # page order; each file draws one section


def _read(relative: str) -> str:
    return (STATIC / relative).read_text(encoding="utf-8")


def render(analysis: dict, tag_info: dict[str, dict]) -> str:
    data = json.dumps({**analysis, "info": tag_info}, ensure_ascii=False).replace("</", "<\\/")
    script = "\n".join([_read("app.js")] + [_read(f"sections/{name}.js") for name in SECTIONS])
    page = _read("page.html").replace("/*CSS*/", _read("style.css")).replace("/*JS*/", script)
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
