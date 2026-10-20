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
        c2 = self.client()
        key = hashlib.sha256(f"{c2.fingerprint}\nAlbum: X by Y".encode()).hexdigest()
        self.assertEqual(c2.cache.get(key), {"label": "y|x", "scores": {"punk": 1.7}, "confidence": {"punk": 0.9}, "fingerprint": c2.fingerprint})

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

    def test_changed_buckets_do_not_reuse_stale_scores(self):
        self.client().score("t", "l")
        changed = {"punk": {**BUCKETS["punk"], "description": "Different."}}
        JevClient(changed, cache_path=self.path, client=self.sdk).score("t", "l")
        self.assertEqual(self.sdk.system_one.call_count, 2)
        # both entries survive, and the original buckets still hit
        self.client().score("t", "l")
        self.assertEqual(self.sdk.system_one.call_count, 2)

    def test_unchanged_buckets_hit_cache_across_clients(self):
        self.client().score("t", "l")
        self.client().score("t", "l")
        self.assertEqual(self.sdk.system_one.call_count, 1)

    def test_fallback_bucket_does_not_change_fingerprint(self):
        self.assertEqual(jev.fingerprint(BUCKETS), jev.fingerprint({**BUCKETS, "other": {"description": "x"}}))

    def _write_legacy(self):
        import json
        legacy = {"label": "l", "scores": {"punk": 0.5}, "confidence": {"punk": 1.0}}
        with open(self.path, "w") as f:
            json.dump({hashlib.sha256(b"t").hexdigest(): legacy}, f)
        return legacy

    def test_legacy_entry_is_migrated_not_discarded(self):
        legacy = self._write_legacy()
        c = self.client()
        self.assertEqual(c.score("t", "l"), {"punk": 0.5})
        self.sdk.system_one.assert_not_called()
        data = self.client().cache.data
        self.assertEqual(data[hashlib.sha256(b"t").hexdigest()], legacy)  # original kept
        self.assertEqual(len(data), 2)
        self.assertEqual(self.client().score("t", "l"), {"punk": 0.5})
        self.sdk.system_one.assert_not_called()

    def test_legacy_entry_with_different_bucket_keys_is_not_adopted(self):
        self._write_legacy()
        other = {"doom": {"description": "Slow."}}
        self.sdk.system_one.return_value.scores = {"doom": mock.Mock(score=2.0, confidence=1.0)}
        c = JevClient(other, cache_path=self.path, client=self.sdk)
        self.assertEqual(c.score("t", "l"), {"doom": 2.0})
        self.assertEqual(self.sdk.system_one.call_count, 1)
        self.assertIn(hashlib.sha256(b"t").hexdigest(), c.cache.data)

    def test_refresh_ignores_existing_cache(self):
        self.client().score("t", "l")
        self.client(refresh=True).score("t", "l")
        self.assertEqual(self.sdk.system_one.call_count, 2)


if __name__ == "__main__":
    unittest.main()
