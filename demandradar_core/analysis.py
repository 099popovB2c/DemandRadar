"""Demand intent detection, deduplication, clustering and opportunity scoring."""

import math
import re
import time
import urllib.parse
from collections import Counter

STOP_WORDS = set(
    "a an the and or to of for in on with is are was were be this that it i you we they "
    "my our your app software tool program need want looking alternative wish there like "
    "have has had can could would should".split()
)

INTENT_PATTERNS = [
    ("buying", re.compile(r"\bwould pay\b|\bpay for\b|\bbudget for\b", re.I), 5),
    ("wish", re.compile(r"\bwish there (?:was|were)\b", re.I), 5),
    (
        "solution_request",
        re.compile(r"\bis there an? (?:app|tool|software)\b|\bneed an? (?:app|tool|software)\b", re.I),
        4,
    ),
    ("searching", re.compile(r"\blooking for\b", re.I), 3),
    ("replacement", re.compile(r"\balternative to\b|\breplacement for\b", re.I), 3),
    (
        "pain",
        re.compile(r"\bcan't find\b|\bcannot find\b|\bfrustrat(?:ed|ing)\b|\bhate\b|\bannoy(?:ed|ing)\b", re.I),
        3,
    ),
    ("workaround", re.compile(r"\bmanual(?:ly)?\b|\bspreadsheet\b|\bworkaround\b", re.I), 1),
]


def canonical_url(url):
    """Normalize a URL for coarse duplicate detection."""
    try:
        parsed = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "")
        )
    except (TypeError, ValueError):
        return str(url or "")


def dedupe(items):
    """Remove duplicate signals by canonical URL or normalized title."""
    output = []
    seen = set()
    for item in items:
        key = canonical_url(item.get("url", ""))
        if not key:
            key = re.sub(r"\W+", " ", item.get("title", "").lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def tokens(text):
    """Tokenize text into simple Unicode-aware lexical features."""
    found = re.findall(r"[^\W_][\w+._-]{2,}", str(text).lower(), flags=re.UNICODE)
    return [token for token in found if token not in STOP_WORDS and not token.startswith("http")]


def vector(item):
    text = (item.get("title", "") + " ") * 2 + item.get("text", "")
    return Counter(tokens(text))


def cosine(left, right):
    """Return cosine similarity for two Counter vectors."""
    common = set(left) & set(right)
    dot = sum(left[key] * right[key] for key in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def intent_tags(item):
    text = f"{item.get('title', '')} {item.get('text', '')}"
    return sorted({name for name, pattern, _weight in INTENT_PATTERNS if pattern.search(text)})


def intent_score(item):
    text = f"{item.get('title', '')} {item.get('text', '')}"
    score = sum(weight for _name, pattern, weight in INTENT_PATTERNS if pattern.search(text))
    return min(10, score)


def freshness(created, now=None):
    """Map item age to a 0..1 freshness score over a one-year horizon."""
    if not created:
        return 0.5
    now = time.time() if now is None else now
    try:
        age_days = max(0.0, (float(now) - float(created)) / 86400)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, 1.0 - age_days / 365)


def excerpt(item, limit=180):
    text = re.sub(r"\s+", " ", item.get("text", "")).strip() or item.get("title", "")
    return text[:limit] + ("…" if len(text) > limit else "")


def _cluster(items, threshold):
    groups = []
    for raw in dedupe(items):
        item = dict(raw)
        item["intent_score"] = intent_score(item)
        item["intent_tags"] = intent_tags(item)
        item["freshness"] = round(freshness(item.get("created")), 3)
        item_vector = vector(item)

        best_group = None
        best_similarity = 0.0
        for group in groups:
            similarity = cosine(item_vector, group["vector"])
            if similarity > best_similarity:
                best_group = group
                best_similarity = similarity

        if best_group is not None and best_similarity >= threshold:
            best_group["items"].append(item)
            best_group["vector"].update(item_vector)
        else:
            groups.append({"items": [item], "vector": Counter(item_vector)})
    return groups


def _opportunity_from_group(group):
    items = group["items"]
    sources = sorted({item["source"] for item in items})
    engagement = sum(
        min(5000, max(0, item.get("score", 0)) + 2 * max(0, item.get("comments", 0)))
        for item in items
    )
    demand_intent = round(sum(item["intent_score"] for item in items) / len(items), 2)
    fresh = round(sum(item["freshness"] for item in items) / len(items), 2)

    components = {
        "frequency": min(100, len(items) * 18),
        "engagement": min(100, math.log1p(engagement) * 13),
        "source_diversity": min(100, len(sources) * 30),
        "intent": demand_intent * 10,
        "freshness": fresh * 100,
    }
    score = round(
        0.28 * components["frequency"]
        + 0.24 * components["engagement"]
        + 0.18 * components["source_diversity"]
        + 0.20 * components["intent"]
        + 0.10 * components["freshness"],
        1,
    )

    all_tokens = Counter()
    for item in items:
        all_tokens.update(tokens((item.get("title", "") + " ") * 2 + item.get("text", "")))
    title_tokens = Counter(token for item in items for token in tokens(item.get("title", "")))
    topic = " ".join(token for token, _count in title_tokens.most_common(4)) or "uncategorized"
    topic_key = "-".join(sorted(token for token, _count in all_tokens.most_common(6))) or "uncategorized"
    intent_mix = Counter(tag for item in items for tag in item["intent_tags"])

    examples = sorted(
        items,
        key=lambda item: item["intent_score"] * 15 + item.get("score", 0) + 2 * item.get("comments", 0),
        reverse=True,
    )[:5]

    return {
        "topic": topic,
        "topic_key": topic_key,
        "mentions": len(items),
        "engagement": engagement,
        "sources": sources,
        "demand_intent": demand_intent,
        "intent_mix": dict(intent_mix),
        "freshness": fresh,
        "opportunity_score": score,
        "components": {key: round(value, 1) for key, value in components.items()},
        "examples": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "intent_score": item["intent_score"],
                "intent_tags": item["intent_tags"],
                "excerpt": excerpt(item),
            }
            for item in examples
        ],
    }


def rank(items, threshold=0.20):
    """Cluster signals and return opportunities sorted by opportunity score."""
    opportunities = [_opportunity_from_group(group) for group in _cluster(items, threshold)]
    return sorted(opportunities, key=lambda row: row["opportunity_score"], reverse=True)
