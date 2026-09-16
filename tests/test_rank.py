import tempfile
import time
import unittest
from pathlib import Path

import demandradar as d


class RankTests(unittest.TestCase):
    def test_rank_returns_expected_fields(self):
        rows = d.rank(d.demo())
        self.assertTrue(rows)
        self.assertIn("topic_key", rows[0])
        self.assertIn("intent_mix", rows[0])
        self.assertIn("components", rows[0])

    def test_buying_intent_is_detected(self):
        tags = d.intent_tags({"title": "I would pay for a tool", "text": ""})
        self.assertIn("buying", tags)

    def test_dedupe_ignores_query_string(self):
        item = {
            "title": "x",
            "text": "",
            "url": "https://e.com/a?x=1",
            "source": "reddit",
            "score": 0,
            "comments": 0,
            "created": time.time(),
        }
        duplicate = dict(item, url="https://e.com/a?x=2")
        self.assertEqual(len(d.dedupe([item, duplicate])), 1)

    def test_saved_search_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.json"
            d.save_search(path, "ideas", ["abc"], ["reddit"], 5, 0.2, 1)
            self.assertIn("ideas", d.load_json(path, {})["searches"])

    def test_trend_annotation(self):
        rows = d.rank(d.demo())
        previous = {
            "opportunities": [
                dict(rows[0], opportunity_score=max(0, rows[0]["opportunity_score"] - 20))
            ]
        }
        d.add_trends(rows, previous)
        self.assertIn(rows[0]["trend"]["state"], {"rising", "stable", "falling", "new"})

    def test_alerts_can_be_forced_for_smoke_test(self):
        rows = d.add_trends(d.rank(d.demo()), None)
        self.assertTrue(d.alerts(rows, 0, 0))


if __name__ == "__main__":
    unittest.main()
