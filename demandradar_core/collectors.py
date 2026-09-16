"""Public-source collectors and graceful multi-source collection."""

import os
import time
import urllib.parse
from datetime import datetime

from .analysis import dedupe
from .http import fetch_json


def iso_epoch(value):
    """Convert an ISO timestamp to epoch seconds when possible."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def reddit(query, limit=30, fetcher=None):
    """Collect recent public Reddit search results for *query*."""
    fetcher = fetcher or fetch_json
    url = (
        "https://www.reddit.com/search.json?q="
        + urllib.parse.quote(query)
        + f"&sort=new&limit={min(int(limit), 100)}&t=year"
    )
    data = fetcher(url)
    rows = []
    for child in data.get("data", {}).get("children", []):
        item = child.get("data", {})
        rows.append(
            {
                "source": "reddit",
                "title": item.get("title", ""),
                "text": item.get("selftext", ""),
                "url": "https://reddit.com" + item.get("permalink", ""),
                "score": int(item.get("score") or 0),
                "comments": int(item.get("num_comments") or 0),
                "created": item.get("created_utc"),
            }
        )
    return rows


def hackernews(query, limit=30, fetcher=None):
    """Collect recent Hacker News stories through the Algolia HN API."""
    fetcher = fetcher or fetch_json
    url = (
        "https://hn.algolia.com/api/v1/search_by_date?query="
        + urllib.parse.quote(query)
        + f"&tags=story&hitsPerPage={min(int(limit), 100)}"
    )
    data = fetcher(url)
    rows = []
    for item in data.get("hits", []):
        object_id = item.get("objectID", "")
        rows.append(
            {
                "source": "hn",
                "title": item.get("title") or "",
                "text": item.get("story_text") or "",
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                "score": int(item.get("points") or 0),
                "comments": int(item.get("num_comments") or 0),
                "created": item.get("created_at_i"),
            }
        )
    return rows


def github(query, limit=30, fetcher=None):
    """Collect public GitHub Issues matching *query*."""
    fetcher = fetcher or fetch_json
    headers = {}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    search = urllib.parse.quote(query + " is:issue")
    url = (
        f"https://api.github.com/search/issues?q={search}"
        f"&per_page={min(int(limit), 100)}&sort=created&order=desc"
    )
    data = fetcher(url, headers=headers)
    rows = []
    for item in data.get("items", []):
        rows.append(
            {
                "source": "github",
                "title": item.get("title", ""),
                "text": item.get("body") or "",
                "url": item.get("html_url", ""),
                "score": int(item.get("reactions", {}).get("total_count") or 0),
                "comments": int(item.get("comments") or 0),
                "created": iso_epoch(item.get("created_at")),
            }
        )
    return rows


COLLECTORS = {
    "reddit": reddit,
    "hn": hackernews,
    "github": github,
}


def collect(queries, sources, limit=30, pause=0.35, collector_map=None):
    """Collect all requested sources while isolating individual source failures.

    A failed source/query pair is recorded in coverage metadata and collection continues
    with the remaining pairs. This is intentional graceful degradation.
    """
    collector_map = collector_map or COLLECTORS
    items = []
    coverage = {
        "attempted": 0,
        "successful": 0,
        "failed": [],
        "by_source": {source: 0 for source in sources},
    }

    for query in queries:
        for source in sources:
            coverage["attempted"] += 1
            collector = collector_map.get(source)
            if collector is None:
                coverage["failed"].append(
                    {"source": source, "query": query, "error": "unknown collector"}
                )
                continue
            try:
                found = collector(query, limit)
                items.extend(found)
                coverage["successful"] += 1
                coverage["by_source"][source] = coverage["by_source"].get(source, 0) + len(found)
            except Exception as exc:  # source isolation boundary
                coverage["failed"].append(
                    {"source": source, "query": query, "error": str(exc)[:180]}
                )
            finally:
                if pause:
                    time.sleep(max(0.0, float(pause)))

    attempted = coverage["attempted"]
    coverage["success_rate"] = round(coverage["successful"] / attempted, 3) if attempted else 1.0
    return dedupe(items), coverage


# Backward-compatible short name used by older callers.
hn = hackernews
