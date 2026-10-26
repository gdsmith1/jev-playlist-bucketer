"""One dict per playlist song for the dashboard's Full playlist tab."""

from ..models import Group
from ..pipeline import parse_row


def song_dicts(lines: list[str], groups: list[Group]) -> list[dict]:
    """Song index, title, artist, album and the index of its album group, in playlist order."""
    group_of = {index: g for g, group in enumerate(groups) for index in group.rows}
    rows = []
    for index, line in enumerate(lines):
        fields = parse_row(line)
        rows.append({"index": index, "title": fields[1], "artist": fields[0], "album": fields[2], "group": group_of[index]})
    return rows
