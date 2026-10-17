import hashlib
import os
import tempfile
import unittest
from unittest import mock

from typesafe_sdk import Score

from bucketer import jev
from bucketer.jev import JevClient

BUCKETS = {"punk": {"description": "Fast punk.", "levels": ["no", {"summary": "yes", "signals": ["fast"]}], "not_for": "pop punk"}}


def sdk_response(score=1.7, confidence=0.9, input_tokens=10, output_tokens=2):
    return mock.Mock(
        scores={"punk": mock.Mock(score=score, confidence=confidence)},
        usage=mock.Mock(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class JevClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "jev_cache.json")
        self.sdk = mock.Mock()
        self.sdk.system_one.return_value = sdk_response()

    def client(self, **kw):
        return JevClient(BUCKETS, cache_path=self.path, client=self.sdk, **kw)

    def test_scores_caches_by_text_hash_and_tracks_usage(self):
        c = self.client()
        self.assertEqual(c.score("Album: X by Y", "y|x"), {"punk": 1.7})
        self.assertEqual(c.score("Album: X by Y", "y|x"), {"punk": 1.7})
        self.assertEqual(self.sdk.system_one.call_count, 1)
        self.assertEqual(c.usage, {"input_tokens": 10, "output_tokens": 2, "call_count": 1})
        entry = self.client().cache.get(hashlib.sha256(b"Album: X by Y").hexdigest())
        self.assertEqual(entry, {"label": "y|x", "scores": {"punk": 1.7}, "confidence": {"punk": 0.9}})

    def test_request_sends_state_and_score_questions(self):
        self.client().score("t", "l")
        kwargs = self.sdk.system_one.call_args.kwargs
        self.assertEqual(kwargs["state"], "t")
        question = kwargs["questions"]["punk"]
        self.assertIsInstance(question, Score)
        self.assertEqual(list(question.criteria), BUCKETS["punk"]["levels"])
        self.assertTrue(question.instructions.endswith("Not for: pop punk"))

    def test_unreported_usage_counts_as_zero(self):
        self.sdk.system_one.return_value = sdk_response(input_tokens=None, output_tokens=None)
        c = self.client()
        c.score("t", "l")
        self.assertEqual(c.usage["input_tokens"], 0)

    def test_retry_policy_only_covers_not_processed_statuses(self):
        self.assertEqual(jev.RETRY.http_statuses, {429, 502, 503, 504})

    def test_missing_key_only_matters_on_cache_miss(self):
        self.client().score("t", "l")
        with mock.patch.dict(os.environ, {}, clear=True):
            offline = JevClient(BUCKETS, cache_path=self.path)
            self.assertEqual(offline.score("t", "l"), {"punk": 1.7})
            with self.assertRaises(SystemExit):
                offline.score("other", "l")

    def test_refresh_ignores_existing_cache(self):
        self.client().score("t", "l")
        self.client(refresh=True).score("t", "l")
        self.assertEqual(self.sdk.system_one.call_count, 2)


if __name__ == "__main__":
    unittest.main()
