"""The step between the dashboard and jev: choose which suggested buckets to score against, and confirm the spend."""

import json
import os
import re
import sys

import questionary

from .jev import FALLBACK_BUCKET

SELECTED_PATH = "selected_buckets.json"
DESCRIPTION_TAGS = 5
CHOICE_TAGS = 4
SAMPLE_TEXTS = 3


def bucket_key(seed: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", seed.lower()).strip("_") or "bucket"
    if base == FALLBACK_BUCKET:
        base = f"{base}_genre"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def describe(tags: list[str], artists: list[str]) -> str:
    text = "Albums tagged " + ", ".join(tags[:DESCRIPTION_TAGS])
    if artists:
        text += ", in the vein of " + ", ".join(artists)
    return text + "."


def suggest_buckets(clusters: list[dict]) -> dict[str, dict]:
    """One suggested bucket per cluster, keyed by a slug of the cluster's seed tag."""
    suggested: dict[str, dict] = {}
    for c in clusters:
        key = bucket_key(c["seed"], set(suggested))
        suggested[key] = {"description": describe(c["tags"], c.get("examples", [])), "tags": c["tags"][:CHOICE_TAGS], "albums": c["albums"], "songs": c["songs"]}
    return suggested


def parse_select(spec: str, suggested: dict[str, dict]) -> list[str]:
    if spec.strip().lower() == "all":
        return list(suggested)
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in suggested]
    if unknown:
        raise SystemExit(f"--select: unknown bucket(s) {', '.join(unknown)}. Suggested buckets: {', '.join(suggested)}")
    return wanted


def ask_checkbox(message: str, choices: list[tuple[str, str]]) -> list[str] | None:
    """Returns the ticked values, or None when the user cancels (Ctrl-C)."""
    return questionary.checkbox(message, choices=[questionary.Choice(title, value=value) for title, value in choices]).ask()


def ask_confirm(message: str) -> bool | None:
    return questionary.confirm(message, default=False).ask()


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def choose_buckets(suggested: dict[str, dict], select: str | None) -> dict[str, dict]:
    """The suggested buckets to score against, as {key: {"description": ...}}. Exits rather than choosing nothing."""
    if not suggested:
        raise SystemExit("No bucket suggestions: the albums have too few usable tags to cluster.")
    if select is not None:
        keys = parse_select(select, suggested)
    elif not interactive():
        raise SystemExit("No terminal to ask in. Pass --select all or --select a,b,c (suggested bucket names are in the dashboard).")
    else:
        choices = [(f"{key}  ({b['albums']} albums, {b['songs']} songs)  {', '.join(b['tags'])}", key) for key, b in suggested.items()]
        keys = ask_checkbox("Buckets to score with jev (space to tick, enter to confirm)", choices)
        if keys is None:
            raise SystemExit("Cancelled. Nothing was sent to jev.")
    if not keys:
        raise SystemExit("No buckets selected. Nothing was sent to jev.")
    return {key: {"description": suggested[key]["description"]} for key in keys}


def write_selected(run_dir: str, selected: dict[str, dict]) -> str:
    path = os.path.join(run_dir, SELECTED_PATH)
    with open(path, "w") as f:
        json.dump(selected, f, indent=2)
    return path


def confirm_spend(jev, texts: list[str], bucket_count: int, yes: bool = False, sample: int = SAMPLE_TEXTS) -> None:
    """Show what scoring will cost (calls for albums not already cached) and exit unless the user explicitly proceeds."""
    pending = [t for t in dict.fromkeys(texts) if not jev.is_cached(t)]
    print(f"\njev: {len(pending)} call(s) needed for {len(texts)} album(s) ({len(texts) - len(pending)} cached), each asking {bucket_count} bucket question(s)")
    if not pending:
        return
    for text in pending[:sample]:
        print("  sample input: " + text.replace("\n", "\n                "))
    if yes:
        return
    if not interactive():
        raise SystemExit("No terminal to confirm in. Pass --yes to proceed with the jev calls above.")
    if not ask_confirm(f"Send {len(pending)} call(s) to jev?"):
        raise SystemExit("Not confirmed. Nothing was sent to jev.")
