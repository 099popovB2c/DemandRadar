#!/usr/bin/env python3
"""Saved-search watch runner for DemandRadar."""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from demandradar_core.constants import VERSION
from demandradar_core.storage import load_json

ROOT = Path(__file__).resolve().parent


def safe_name(name):
    """Return a filesystem-safe saved-search directory name."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name)).strip("._-")
    return cleaned or "search"


def snapshots(history_dir, name):
    directory = Path(history_dir) / safe_name(name)
    return sorted(
        (path for path in directory.glob("*.json") if path.name != "index.json"),
        key=lambda path: path.name,
    )


def latest_snapshot(history_dir, name):
    found = snapshots(history_dir, name)
    return found[-1] if found else None


def snapshot_path(history_dir, name, when=None):
    when = when or datetime.now(timezone.utc)
    directory = Path(history_dir) / safe_name(name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / (when.strftime("%Y%m%dT%H%M%SZ") + ".json")


def summarize(payload):
    opportunities = payload.get("opportunities", [])
    alerts = payload.get("alerts", [])
    top = opportunities[0] if opportunities else {}
    return {
        "generated_at": payload.get("generated_at"),
        "opportunities": len(opportunities),
        "alerts": len(alerts),
        "top_topic": top.get("topic"),
        "top_score": top.get("opportunity_score"),
        "coverage": payload.get("coverage", {}).get("success_rate"),
    }


def append_alerts(path, payload, search_name):
    alerts = payload.get("alerts", [])
    if not alerts:
        return 0
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for alert in alerts:
            row = {
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "search": search_name,
                **alert,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(alerts)


def update_index(history_dir, name, snapshot, payload, keep=90):
    directory = Path(history_dir) / safe_name(name)
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / "index.json"
    old = load_json(index_path, {"search": name, "runs": []}) or {"search": name, "runs": []}
    runs = [run for run in old.get("runs", []) if run.get("snapshot") != snapshot.name]
    runs.append({"snapshot": snapshot.name, **summarize(payload)})
    runs = sorted(runs, key=lambda run: run["snapshot"])

    if keep > 0 and len(runs) > keep:
        for run in runs[:-keep]:
            old_snapshot = directory / run["snapshot"]
            if old_snapshot.exists():
                old_snapshot.unlink()
        runs = runs[-keep:]

    index = {"version": VERSION, "search": name, "runs": runs}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def build_command(search_name, out, previous=None, saved_file="data/saved_searches.json", demo=False):
    command = [sys.executable, str(ROOT / "demandradar.py")]
    if demo:
        command.append("--demo")
    else:
        command.extend(["--run-saved", search_name, "--saved-file", saved_file])
    if previous:
        command.extend(["--previous", str(previous)])
    command.extend(["--out", str(out)])
    return command


def run_once(
    search_name,
    history_dir="data/history",
    alerts_file="data/alerts.jsonl",
    saved_file="data/saved_searches.json",
    keep=90,
    demo=False,
):
    previous = latest_snapshot(history_dir, search_name)
    output = snapshot_path(history_dir, search_name)
    command = build_command(search_name, output, previous, saved_file, demo)
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        output.unlink(missing_ok=True)
        message = result.stderr or result.stdout or f"DemandRadar exited {result.returncode}"
        raise RuntimeError(message.strip())

    payload = load_json(output, {}) or {}
    if not isinstance(payload.get("opportunities", []), list):
        output.unlink(missing_ok=True)
        raise RuntimeError("Invalid DemandRadar snapshot")

    logged = append_alerts(alerts_file, payload, search_name)
    index = update_index(history_dir, search_name, output, payload, keep)
    return {
        "snapshot": str(output),
        "alerts_logged": logged,
        "summary": summarize(payload),
        "runs_kept": len(index["runs"]),
    }


def print_history(history_dir, name, limit=20):
    index = load_json(
        Path(history_dir) / safe_name(name) / "index.json",
        {"runs": []},
    ) or {"runs": []}
    rows = index.get("runs", [])[-max(1, int(limit)) :]
    print(json.dumps({"search": name, "runs": rows}, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description=f"DemandRadar v{VERSION} watch runner")
    parser.add_argument("--search", default="software-ideas", help="saved search name")
    parser.add_argument("--saved-file", default="data/saved_searches.json")
    parser.add_argument("--history-dir", default="data/history")
    parser.add_argument("--alerts-file", default="data/alerts.jsonl")
    parser.add_argument("--keep", type=int, default=90)
    parser.add_argument("--interval-minutes", type=int, default=0, help="0 = run once")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--history-limit", type=int, default=20)
    parser.add_argument("--demo", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.history:
        print_history(args.history_dir, args.search, args.history_limit)
        return 0

    interval = max(0, args.interval_minutes)
    while True:
        try:
            result = run_once(
                args.search,
                args.history_dir,
                args.alerts_file,
                args.saved_file,
                args.keep,
                args.demo,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[watch] {exc}", file=sys.stderr, flush=True)
            if interval <= 0:
                return 2
        if interval <= 0:
            return 0
        time.sleep(max(60, interval * 60))


if __name__ == "__main__":
    raise SystemExit(main())
