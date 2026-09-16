"""JSON persistence helpers used by the CLI and monitor."""

import json
from pathlib import Path


def load_json(path, default=None):
    """Return decoded JSON or *default* when the file cannot be read safely."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def save_json(path, value):
    """Write JSON atomically enough for local single-process use."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_search(path, name, queries, sources, limit, threshold, min_intent):
    """Create or replace a named saved search configuration."""
    config = load_json(path, {"searches": {}}) or {"searches": {}}
    config.setdefault("searches", {})[name] = {
        "queries": list(queries),
        "sources": list(sources),
        "limit": int(limit),
        "threshold": float(threshold),
        "min_intent": int(min_intent),
    }
    save_json(path, config)
