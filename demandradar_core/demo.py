"""Deterministic-ish demo signals for offline smoke tests."""

import time


def demo(now=None):
    now = time.time() if now is None else float(now)
    return [
        {
            "source": "reddit",
            "title": "Looking for a simple shared budget app for couples",
            "text": "We need something easier than a spreadsheet and would pay for a simple option.",
            "url": "https://reddit.com/a",
            "score": 146,
            "comments": 71,
            "created": now - 86400 * 5,
        },
        {
            "source": "reddit",
            "title": "Is there an offline Google Photos alternative?",
            "text": "Local timeline and duplicate finder would be enough.",
            "url": "https://reddit.com/b",
            "score": 91,
            "comments": 43,
            "created": now - 86400 * 20,
        },
        {
            "source": "github",
            "title": "Feature request: visual repository health report",
            "text": "Need a tool to check docs, secrets, outdated deps and CI.",
            "url": "https://github.com/x/issues/1",
            "score": 44,
            "comments": 12,
            "created": now - 86400 * 35,
        },
        {
            "source": "hn",
            "title": "Ask HN: looking for simple self-hosted family budget",
            "text": "Need CSV import and shared household categories.",
            "url": "https://news.ycombinator.com/item?id=1",
            "score": 63,
            "comments": 32,
            "created": now - 86400 * 8,
        },
    ]
