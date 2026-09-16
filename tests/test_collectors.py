import unittest

from demandradar_core.collectors import collect, github, hackernews, reddit


class CollectorTests(unittest.TestCase):
    def test_reddit_normalization(self):
        payload = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Need a budget app",
                            "selftext": "Looking for something simple",
                            "permalink": "/r/test/comments/1/x/",
                            "score": 12,
                            "num_comments": 4,
                            "created_utc": 123,
                        }
                    }
                ]
            }
        }
        rows = reddit("budget", fetcher=lambda _url: payload)
        self.assertEqual(rows[0]["source"], "reddit")
        self.assertTrue(rows[0]["url"].startswith("https://reddit.com/"))
        self.assertEqual(rows[0]["comments"], 4)

    def test_hackernews_normalization(self):
        payload = {
            "hits": [
                {
                    "title": "Ask HN: tool?",
                    "story_text": "Need a tool",
                    "objectID": "42",
                    "points": 8,
                    "num_comments": 2,
                    "created_at_i": 321,
                }
            ]
        }
        rows = hackernews("tool", fetcher=lambda _url: payload)
        self.assertEqual(rows[0]["source"], "hn")
        self.assertIn("item?id=42", rows[0]["url"])

    def test_github_normalization_and_optional_headers(self):
        payload = {
            "items": [
                {
                    "title": "Feature request",
                    "body": "Need software",
                    "html_url": "https://github.com/a/b/issues/1",
                    "reactions": {"total_count": 3},
                    "comments": 5,
                    "created_at": "2026-09-16T00:00:00Z",
                }
            ]
        }
        seen = {}

        def fetcher(url, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return payload

        rows = github("feature", fetcher=fetcher)
        self.assertEqual(rows[0]["source"], "github")
        self.assertEqual(rows[0]["score"], 3)
        self.assertIn("is%3Aissue", seen["url"])

    def test_collection_degrades_when_one_source_fails(self):
        def ok(_query, _limit):
            return [
                {
                    "source": "reddit",
                    "title": "Need an app",
                    "text": "",
                    "url": "https://example.test/1",
                    "score": 1,
                    "comments": 0,
                    "created": 1,
                }
            ]

        def fail(_query, _limit):
            raise RuntimeError("rate limited")

        items, coverage = collect(
            ["idea"],
            ["reddit", "hn"],
            10,
            pause=0,
            collector_map={"reddit": ok, "hn": fail},
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(coverage["attempted"], 2)
        self.assertEqual(coverage["successful"], 1)
        self.assertEqual(coverage["success_rate"], 0.5)
        self.assertEqual(coverage["failed"][0]["source"], "hn")

    def test_unknown_collector_is_reported_not_raised(self):
        items, coverage = collect(["idea"], ["unknown"], pause=0, collector_map={})
        self.assertEqual(items, [])
        self.assertEqual(coverage["successful"], 0)
        self.assertEqual(coverage["failed"][0]["error"], "unknown collector")


if __name__ == "__main__":
    unittest.main()
