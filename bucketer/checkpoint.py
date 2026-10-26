"""The step between the dashboard and jev: choose which suggested buckets to score against, and confirm the spend."""

import json
import os
import re
import sys

import questionary

from .jev import FALLBACK_BUCKET

SELECTED_PATH = "selected_buckets.json"
RECOMMENDED_PATH = "recommended_buckets.json"
CUSTOM_DEFAULT = "buckets.json"
SKIP_VALUE = "__skip_recommended__"
SKIP_TITLE = "Skip recommended buckets (use a custom file only)"
CUSTOM_PROMPT = f"Custom bucket file (path relative to the repo root, blank for none; recommended location: {CUSTOM_DEFAULT})"
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


def example_artists(examples: list[dict]) -> list[str]:
    artists: list[str] = []
    for e in examples:
        if e["artist"] not in artists:
            artists.append(e["artist"])
    return artists


def suggest_buckets(clusters: list[dict]) -> dict[str, dict]:
    """One suggested bucket per cluster, keyed by a slug of the cluster's seed tag."""
    suggested: dict[str, dict] = {}
    for c in clusters:
        key = bucket_key(c["seed"], set(suggested))
        suggested[key] = {"description": describe(c["tags"], example_artists(c.get("examples", []))), "tags": c["tags"][:CHOICE_TAGS], "albums": c["albums"], "songs": c["songs"]}
    return suggested


def parse_select(spec: str, suggested: dict[str, dict]) -> list[str]:
    if spec.strip().lower() == "all":
        return list(suggested)
    if spec.strip().lower() == "none":
        return []
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in suggested]
    if unknown:
        raise SystemExit(f"--select: unknown bucket(s) {', '.join(unknown)}. Suggested buckets: {', '.join(suggested)}")
    return wanted


def ask_checkbox(message: str, choices: list[tuple[str, str]]) -> list[str] | None:
    """Returns the ticked values, or None when the user cancels (Ctrl-C)."""
    return questionary.checkbox(message, choices=[questionary.Choice(title, value=value) for title, value in choices]).ask()


def ask_text(message: str, default: str = "") -> str | None:
    return questionary.text(message, default=default).ask()


def ask_confirm(message: str) -> bool | None:
    return questionary.confirm(message, default=False).ask()


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def write_recommended(run_dir: str, suggested: dict[str, dict]) -> str:
    path = os.path.join(run_dir, RECOMMENDED_PATH)
    with open(path, "w") as f:
        json.dump(suggested, f, indent=2)
    return path


def copy_hint(run_dir: str) -> str:
    return f"to customize: cp {os.path.join(run_dir, RECOMMENDED_PATH)} {CUSTOM_DEFAULT}, then edit the descriptions (tags/albums/songs are ignored)"


def load_custom(path: str, taken: set[str], run_dir: str | None = None) -> dict[str, dict]:
    """Custom buckets from a JSON file of {key: {"description": str}}."""
    if not os.path.isfile(path):
        hint = f"\n{copy_hint(run_dir)}" if run_dir else ""
        raise SystemExit(f"Custom bucket file not found: {path}{hint}")
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path}: not valid JSON ({e})")
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: must be a JSON object of {{bucket: {{\"description\": ...}}}}")
    custom: dict[str, dict] = {}
    for key, bucket in data.items():
        if key == FALLBACK_BUCKET:
            raise SystemExit(f"{path}: bucket name '{FALLBACK_BUCKET}' is reserved for albums that match nothing")
        if key in taken:
            raise SystemExit(f"{path}: bucket '{key}' collides with a chosen recommended bucket; rename it or deselect the recommended one")
        description = bucket.get("description") if isinstance(bucket, dict) else None
        if not isinstance(description, str) or not description.strip():
            raise SystemExit(f"{path}: bucket '{key}' needs a non-empty \"description\"")
        custom[key] = {"description": description.strip()}
    return custom


def choose_buckets(suggested: dict[str, dict], select: str | None, buckets_path: str | None = None, run_dir: str | None = None) -> dict[str, dict]:
    """Recommended plus custom buckets as {key: {"description": ..., "source": ...}}. Exits rather than choosing nothing."""
    asked = False
    if select is not None:
        keys = parse_select(select, suggested)
    elif buckets_path is not None and not suggested:
        keys = []
    elif not interactive():
        if buckets_path is None:
            raise SystemExit("No terminal to ask in. Pass --select all|none|a,b,c and/or --buckets PATH (suggested bucket names are in the dashboard).")
        keys = []
    else:
        asked = True
        choices = [(f"{key}  ({b['albums']} albums, {b['songs']} songs)  {', '.join(b['tags'])}", key) for key, b in suggested.items()]
        choices.append((SKIP_TITLE, SKIP_VALUE))
        keys = ask_checkbox("Recommended buckets to score with jev (space to tick, enter to confirm)", choices) if suggested else []
        if keys is None:
            raise SystemExit("Cancelled. Nothing was sent to jev.")
        if SKIP_VALUE in keys:
            keys = []
    chosen = {key: {"description": suggested[key]["description"], "source": "recommended"} for key in keys}
    if buckets_path is None and asked:
        answer = ask_text(CUSTOM_PROMPT, default="")
        if answer is None:
            raise SystemExit("Cancelled. Nothing was sent to jev.")
        buckets_path = answer.strip() or None
    if buckets_path:
        chosen.update({k: {**b, "source": "custom"} for k, b in load_custom(buckets_path, set(chosen), run_dir).items()})
    if not chosen:
        raise SystemExit("No buckets selected. Nothing was sent to jev.")
    return chosen


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
