"""Snapshot comparison and alert generation."""


def _topic_tokens(row):
    raw = row.get("topic_key") or row.get("topic", "")
    return set(str(raw).replace("-", " ").split())


def match_old(row, old_rows, minimum_similarity=0.35):
    """Return the most similar previous opportunity above a Jaccard threshold."""
    current = _topic_tokens(row)
    best = None
    best_score = 0.0
    for old in old_rows:
        previous = _topic_tokens(old)
        union = current | previous
        similarity = len(current & previous) / len(union) if union else 0.0
        if similarity > best_score:
            best = old
            best_score = similarity
    return best if best_score >= minimum_similarity else None


def add_trends(rows, previous):
    """Annotate opportunities as new, rising, stable or falling."""
    old_rows = (previous or {}).get("opportunities", [])
    for row in rows:
        old = match_old(row, old_rows)
        if not old:
            row["trend"] = {
                "state": "new",
                "previous_score": None,
                "score_delta": None,
                "mentions_delta": None,
            }
            continue

        score_delta = round(
            float(row.get("opportunity_score", 0)) - float(old.get("opportunity_score", 0)),
            1,
        )
        mentions_delta = int(row.get("mentions", 0)) - int(old.get("mentions", 0))
        if score_delta >= 5:
            state = "rising"
        elif score_delta <= -5:
            state = "falling"
        else:
            state = "stable"
        row["trend"] = {
            "state": state,
            "previous_score": old.get("opportunity_score"),
            "score_delta": score_delta,
            "mentions_delta": mentions_delta,
        }
    return rows


def alerts(rows, score=70, rise=10):
    """Return actionable alerts for strong, rising or new high-intent clusters."""
    output = []
    for row in rows:
        reasons = []
        trend = row.get("trend", {"state": "new", "score_delta": None})
        if row.get("opportunity_score", 0) >= score:
            reasons.append(f"score>={score}")
        delta = trend.get("score_delta")
        if delta is not None and delta >= rise:
            reasons.append(f"score rose {delta:+.1f}")
        if trend.get("state") == "new" and row.get("demand_intent", 0) >= 5:
            reasons.append("new high-intent cluster")
        if reasons:
            output.append(
                {
                    "topic": row.get("topic", "uncategorized"),
                    "opportunity_score": row.get("opportunity_score", 0),
                    "reasons": reasons,
                    "examples": row.get("examples", [])[:2],
                }
            )
    return output
