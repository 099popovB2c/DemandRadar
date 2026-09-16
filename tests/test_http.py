import json
import unittest
import urllib.error
from email.message import Message

from demandradar_core.http import fetch_json


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class HttpTests(unittest.TestCase):
    def test_retries_http_429_and_honors_retry_after(self):
        calls = []
        sleeps = []
        headers = Message()
        headers["Retry-After"] = "0"

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            if len(calls) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, "rate limited", headers, None)
            return FakeResponse({"ok": True})

        result = fetch_json(
            "https://example.test/data",
            retries=1,
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [0.0])

    def test_does_not_retry_non_retryable_404(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 404, "missing", Message(), None)

        with self.assertRaises(urllib.error.HTTPError):
            fetch_json("https://example.test/missing", retries=3, opener=opener, sleeper=lambda _x: None)
        self.assertEqual(len(calls), 1)

    def test_retries_network_error(self):
        calls = []
        sleeps = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.URLError("temporary")
            return FakeResponse({"ok": 1})

        result = fetch_json(
            "https://example.test/data",
            retries=1,
            backoff=0.25,
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(result, {"ok": 1})
        self.assertEqual(sleeps, [0.25])

    def test_retries_github_style_rate_limit_403(self):
        calls = []
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Reset"] = "0"

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(request.full_url, 403, "rate limited", headers, None)
            return FakeResponse({"ok": True})

        self.assertEqual(
            fetch_json(
                "https://api.github.com/example",
                retries=1,
                opener=opener,
                sleeper=lambda _x: None,
            ),
            {"ok": True},
        )
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
