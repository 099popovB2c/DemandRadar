#!/usr/bin/env python3
"""DemandRadar command-line entry point and backward-compatible public facade."""

import argparse
import csv
import json
from datetime import datetime, timezone

from demandradar_core.analysis import (
    canonical_url,
    cosine,
    dedupe,
    excerpt,
    freshness,
    intent_score,
    intent_tags,
    rank,
    tokens,
    vector,
)
from demandradar_core.collectors import collect, github, hn, reddit
from demandradar_core.constants import SOFTWARE_REQUEST_TEMPLATES, VERSION
from demandradar_core.demo import demo
from demandradar_core.http import fetch_json
from demandradar_core.storage import load_json, save_json, save_search
from demandradar_core.trends import add_trends, alerts, match_old

TEMPLATES = SOFTWARE_REQUEST_TEMPLATES


def build_parser():
    parser = argparse.ArgumentParser(
        description="Mine repeated software demand from Reddit, Hacker News and GitHub Issues."
    )
    parser.add_argument("--version", action="version", version=f"DemandRadar {VERSION}")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--preset", choices=["software-requests"])
    parser.add_argument("--sources", default="reddit,hn,github")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--threshold", type=float, default=0.20)
    parser.add_argument("--min-intent", type=int, default=0)
    parser.add_argument("--out", default="data/results.json")
    parser.add_argument("--csv")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--saved-file", default="data/saved_searches.json")
    parser.add_argument("--save-search")
    parser.add_argument("--run-saved")
    parser.add_argument("--list-saved", action="store_true")
    parser.add_argument("--previous")
    parser.add_argument("--alert-score", type=float, default=70)
    parser.add_argument("--alert-rise", type=float, default=10)
    return parser


def _resolve_search(args):
    config = load_json(args.saved_file, {"searches": {}}) or {"searches": {}}
    if args.list_saved:
        return config, None, None

    queries = args.query or (TEMPLATES if args.preset else ["software request"])
    sources = [source.strip() for source in args.sources.split(",") if source.strip()]

    if args.run_saved:
        saved = config.get("searches", {}).get(args.run_saved)
        if not saved:
            raise SystemExit(f"Saved search not found: {args.run_saved}")
        queries = list(saved.get("queries", []))
        sources = list(saved.get("sources", []))
        args.limit = int(saved.get("limit", args.limit))
        args.threshold = float(saved.get("threshold", args.threshold))
        args.min_intent = int(saved.get("min_intent", args.min_intent))

    return config, queries, sources


def _write_csv(path, rows):
    fields = [
        "topic",
        "mentions",
        "engagement",
        "sources",
        "demand_intent",
        "freshness",
        "opportunity_score",
        "trend_state",
        "score_delta",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            trend = row.get("trend", {})
            writer.writerow(
                {
                    "topic": row.get("topic"),
                    "mentions": row.get("mentions"),
                    "engagement": row.get("engagement"),
                    "sources": ",".join(row.get("sources", [])),
                    "demand_intent": row.get("demand_intent"),
                    "freshness": row.get("freshness"),
                    "opportunity_score": row.get("opportunity_score"),
                    "trend_state": trend.get("state"),
                    "score_delta": trend.get("score_delta"),
                }
            )


def run(args):
    config, queries, sources = _resolve_search(args)
    if args.list_saved:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    if args.save_search:
        save_search(
            args.saved_file,
            args.save_search,
            queries,
            sources,
            args.limit,
            args.threshold,
            args.min_intent,
        )

    if args.demo:
        items = demo()
        coverage = {
            "attempted": 0,
            "successful": 0,
            "failed": [],
            "by_source": {},
            "success_rate": 1.0,
        }
    else:
        items, coverage = collect(queries, sources, args.limit)

    items = [item for item in items if intent_score(item) >= args.min_intent]
    previous = load_json(args.previous, None) if args.previous else None
    opportunities = add_trends(rank(items, args.threshold), previous)
    found_alerts = alerts(opportunities, args.alert_score, args.alert_rise)

    payload = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queries": queries,
        "sources": sources,
        "coverage": coverage,
        "items": items,
        "opportunities": opportunities,
        "alerts": found_alerts,
    }
    save_json(args.out, payload)

    if args.csv:
        _write_csv(args.csv, opportunities)

    print(
        f"Saved {len(items)} signals, {len(opportunities)} groups and "
        f"{len(found_alerts)} alerts to {args.out}"
    )
    for alert in found_alerts[:10]:
        reasons = ", ".join(alert.get("reasons", []))
        print(f"ALERT {alert['opportunity_score']:>5.1f} {alert['topic']}: {reasons}")
    return 0


def main(argv=None):
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
