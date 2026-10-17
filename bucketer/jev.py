"""jev client (official typesafe-sdk): one score question per bucket, per-album results cached on disk. This is the call that spends tokens."""

import hashlib
import os
from typing import Any

from typesafe_sdk import RetryPolicy, Score, TypeSafeClient

from .cache import JsonCache

JEV_MODEL = "jev-latest"
JEV_TIMEOUT = 120  # total seconds per scoring call, retries included
# Retry only statuses where the service says it did not process the request.
RETRY = RetryPolicy(max_retries=3, http_statuses={429, 502, 503, 504}, timeout=JEV_TIMEOUT)

# Albums that clear no bucket's threshold land here. jev never sees it: it is not a question,
# and any bucket with this name in buckets.json is ignored.
FALLBACK_BUCKET = "other"

GENERIC_LEVELS = [
    "Does not fit this bucket at all",
    "Fits this bucket somewhat",
    "Strongly fits this bucket",
]


def build_questions(buckets: dict) -> dict[str, Score]:
    """One score question per bucket ("other" is the fallback, not a judgment).
    A bucket may define `levels` (2-10 strings or {summary, signals}) and `not_for`
    (lookalikes that do not belong); otherwise generic levels are used."""
    questions = {}
    for key, bucket in buckets.items():
        if key == FALLBACK_BUCKET:
            continue
        instructions = f"Does the album described in `state` fit this genre bucket? {bucket['description']}"
        if bucket.get("not_for"):
            instructions += f" Not for: {bucket['not_for']}"
        questions[key] = Score(instructions=instructions, criteria=bucket.get("levels") or GENERIC_LEVELS)
    return questions


class JevClient:
    def __init__(self, buckets: dict, cache_path: str = "jev_cache.json", refresh: bool = False, client: Any = None) -> None:
        self.questions = build_questions(buckets)
        self.cache = JsonCache(cache_path, fresh=refresh)
        self._client = client
        self.usage = {"input_tokens": 0, "output_tokens": 0, "call_count": 0}

    def _sdk(self) -> Any:
        if self._client is None:
            api_key = os.environ.get("TYPESAFE_API_KEY")
            if not api_key:
                raise SystemExit("TYPESAFE_API_KEY is not set (needed to score with jev; not needed with --dry-run)")
            self._client = TypeSafeClient(api_key=api_key, model=JEV_MODEL, retry=RETRY)
        return self._client

    def score(self, text: str, label: str) -> dict[str, float]:
        """Scores per bucket for the album `text`. Cached by the sha256 of the exact text."""
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if cache_key in self.cache:
            return self.cache.get(cache_key)["scores"]

        response = self._sdk().system_one(state=text, questions=self.questions)
        scores = {key: answer.score for key, answer in response.scores.items()}
        confidence = {key: answer.confidence for key, answer in response.scores.items()}

        self.usage["input_tokens"] += response.usage.input_tokens or 0
        self.usage["output_tokens"] += response.usage.output_tokens or 0
        self.usage["call_count"] += 1

        self.cache.set(cache_key, {"label": label, "scores": scores, "confidence": confidence})
        self.cache.flush()
        return scores
