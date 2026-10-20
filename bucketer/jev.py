"""jev client (official typesafe-sdk): one score question per bucket, per-album results cached on disk. This is the call that spends tokens."""

import hashlib
import json
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
        instructions, criteria = question_spec(bucket)
        questions[key] = Score(instructions=instructions, criteria=criteria)
    return questions


def question_spec(bucket: dict) -> tuple[str, list]:
    instructions = f"Does the album described in `state` fit this genre bucket? {bucket['description']}"
    if bucket.get("not_for"):
        instructions += f" Not for: {bucket['not_for']}"
    return instructions, bucket.get("levels") or GENERIC_LEVELS


def fingerprint(buckets: dict) -> str:
    """Hash of everything jev is asked: bucket keys, instruction text and levels ("other" excluded).
    Any change to the question set changes it, so cached scores are never reused for different questions."""
    spec = {key: question_spec(b) for key, b in sorted(buckets.items()) if key != FALLBACK_BUCKET}
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class JevClient:
    def __init__(self, buckets: dict, cache_path: str = "jev_cache.json", refresh: bool = False, client: Any = None) -> None:
        self.questions = build_questions(buckets)
        self.fingerprint = fingerprint(buckets)
        self.cache = JsonCache(cache_path, fresh=refresh)
        self._client = client
        self.usage = {"input_tokens": 0, "output_tokens": 0, "call_count": 0}

    def _adoptable(self, entry: dict) -> bool:
        """A legacy entry (no fingerprint) is only trusted if it scored exactly today's bucket keys."""
        return "fingerprint" not in entry and set(entry.get("scores", {})) == set(self.questions)

    def is_cached(self, text: str) -> bool:
        """True when `score(text, ...)` would be answered without a jev call."""
        if self._cache_key(text) in self.cache:
            return True
        legacy = self.cache.get(hashlib.sha256(text.encode("utf-8")).hexdigest())
        return legacy is not None and self._adoptable(legacy)

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self.fingerprint}\n{text}".encode("utf-8")).hexdigest()

    def _sdk(self) -> Any:
        if self._client is None:
            api_key = os.environ.get("TYPESAFE_API_KEY")
            if not api_key:
                raise SystemExit("TYPESAFE_API_KEY is not set (needed to score with jev; not needed with --dry-run)")
            self._client = TypeSafeClient(api_key=api_key, model=JEV_MODEL, retry=RETRY)
        return self._client

    def score(self, text: str, label: str) -> dict[str, float]:
        """Scores per bucket for the album `text`. Cached by the sha256 of the exact text."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = self._cache_key(text)
        if cache_key in self.cache:
            return self.cache.get(cache_key)["scores"]
        legacy = self.cache.get(text_hash)
        if legacy is not None and self._adoptable(legacy):
            # Pre-fingerprint entry, paid for against the buckets in use then. Copy it under the
            # bucket-aware key; the legacy entry stays, so nothing is ever lost.
            self.cache.set(cache_key, {**legacy, "fingerprint": self.fingerprint})
            self.cache.flush()
            return legacy["scores"]

        response = self._sdk().system_one(state=text, questions=self.questions)
        scores = {key: answer.score for key, answer in response.scores.items()}
        confidence = {key: answer.confidence for key, answer in response.scores.items()}

        self.usage["input_tokens"] += response.usage.input_tokens or 0
        self.usage["output_tokens"] += response.usage.output_tokens or 0
        self.usage["call_count"] += 1

        self.cache.set(cache_key, {"label": label, "scores": scores, "confidence": confidence, "fingerprint": self.fingerprint})
        self.cache.flush()
        return scores
