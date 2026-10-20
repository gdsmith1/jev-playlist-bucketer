"""Genre dashboard: turns the Last.fm tags gathered for a run into one self-contained HTML page."""

from .analysis import UMBRELLA_TAGS, album_tags, analyze
from .render import render, write_dashboard

__all__ = ["UMBRELLA_TAGS", "album_tags", "analyze", "render", "write_dashboard"]
