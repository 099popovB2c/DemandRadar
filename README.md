# DemandRadar

[![CI](https://github.com/099popovB2c/DemandRadar/actions/workflows/ci.yml/badge.svg)](https://github.com/099popovB2c/DemandRadar/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/099popovB2c/DemandRadar)](https://github.com/099popovB2c/DemandRadar/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DemandRadar is an open-source demand-mining and opportunity-tracking tool for software ideas.**

It searches public software requests on **Reddit, Hacker News and GitHub Issues**, removes duplicates, groups similar requests, scores demand signals, compares results over time and raises alerts when an opportunity becomes unusually strong or starts rising.

The goal is simple:

> Stop guessing what software people want. Find repeated requests, pain points and replacement searches in public conversations, then track whether demand is growing.

DemandRadar runs locally. It has **no hosted backend, no analytics and no paid AI dependency**.

---

## What DemandRadar does

```text
Reddit + Hacker News + GitHub Issues
                 |
                 v
        Collect public requests
                 |
                 v
          Deduplicate URLs
                 |
                 v
     Detect demand / buying intent
                 |
                 v
   Cluster similar requests together
                 |
                 v
        Calculate opportunity score
                 |
                 v
       Compare with older snapshots
                 |
                 v
      Rising / Falling / New alerts
```

Typical posts DemandRadar is designed to find include:

```text
"Looking for a simple shared budget app for couples"
"Is there an offline Google Photos alternative?"
"I wish there was a simpler PDF editor"
"Need a tool to manage recurring household bills"
"Would pay for a local-first photo organizer"
```

---

## Data sources

DemandRadar currently has collectors for:

| Source | What is searched | Authentication |
| --- | --- | --- |
| Reddit | Public search results | Not required for the current public endpoint |
| Hacker News | Stories through the Algolia HN API | Not required |
| GitHub | Public Issues Search API | Optional `GITHUB_TOKEN` recommended for higher rate limits |

Public endpoints can rate-limit requests. DemandRadar records collector coverage and failures instead of silently hiding missing sources.

---

## Demand intent detection

DemandRadar looks for language that indicates a real need, replacement search, frustration or willingness to pay.

Current signal examples include:

| Signal | Example language | Relative weight |
| --- | --- | ---: |
| Buying intent | `would pay`, `pay for`, `budget for` | 5 |
| Wish / unmet product | `wish there was` | 5 |
| Direct solution request | `is there an app`, `need a tool` | 4 |
| Active search | `looking for` | 3 |
| Replacement search | `alternative to`, `replacement for` | 3 |
| Pain point | `can't find`, `frustrated`, `annoying` | 3 |
| Workaround | `manual`, `spreadsheet`, `workaround` | 1 |

Each collected item receives an intent score and intent tags before clustering.

---

## How clustering works

DemandRadar does **not** require an LLM to group requests.

The current engine:

1. normalizes text;
2. removes common stop words;
3. builds token-frequency vectors;
4. compares requests using **cosine similarity**;
5. merges sufficiently similar requests into the same opportunity cluster.

That means the core pipeline stays lightweight, auditable and inexpensive to run.

The similarity threshold can be adjusted with `--threshold`.

---

## Opportunity score

Each cluster receives an `opportunity_score` from several signals.

Current weighting:

| Component | Weight |
| --- | ---: |
| Repeated mentions / frequency | 28% |
| Engagement | 24% |
| Source diversity | 18% |
| Demand intent | 20% |
| Freshness | 10% |

Conceptually:

```text
Opportunity Score =
  0.28 * Frequency
+ 0.24 * Engagement
+ 0.18 * Source Diversity
+ 0.20 * Demand Intent
+ 0.10 * Freshness
```

A strong opportunity is therefore not just a post with many upvotes. Repetition, intent, recency and appearance across multiple sources all matter.

---

## Trend tracking

DemandRadar can compare a new run with an older snapshot.

A topic is marked as:

- `new`
- `rising`
- `stable`
- `falling`

For matched clusters it stores the previous score, score delta and mentions delta.

Example:

```text
Offline photo manager
Previous score: 61.2
Current score: 77.8
Score delta: +16.6
Trend: rising
```

---

## Alerts

DemandRadar can raise alerts when a cluster crosses an opportunity threshold, rises quickly, or appears as a new high-intent request.

Default alert logic includes:

- opportunity score >= `70`;
- score increase >= `10`;
- new cluster with high demand intent.

Alert thresholds can be changed from the CLI.

The watch runner appends persistent alerts to:

```text
data/alerts.jsonl
```

---

## v0.4.0 watch mode

v0.4.0 adds repeatable monitoring for saved searches.

The watch runner:

- runs saved searches automatically;
- stores timestamped snapshots;
- connects the previous snapshot automatically;
- calculates trend deltas;
- appends persistent alerts;
- keeps a history index;
- prunes old snapshots with retention controls;
- can run once or at a chosen interval.

History layout:

```text
data/
  history/
    <saved-search>/
      20260916T120000Z.json
      20260916T130000Z.json
      index.json
  alerts.jsonl
```

Runtime history and alerts are ignored by Git by default.

---

## Requirements

- Python 3
- Internet access for live collectors
- No third-party Python packages are required for the core project

`requirements.txt` intentionally contains only a note because the current implementation uses the Python standard library.

---

## Quick start

Clone the repository:

```bash
git clone https://github.com/099popovB2c/DemandRadar.git
cd DemandRadar
```

Run a live search:

```bash
python demandradar.py --query "photo manager" --query "shared budget"
```

Results are written to:

```text
data/results.json
```

---

## Search specific sources

```bash
python demandradar.py \
  --query "Google Photos alternative" \
  --sources reddit,hn,github \
  --limit 30
```

Available source names:

```text
reddit
hn
github
```

---

## Use the built-in software-request preset

```bash
python demandradar.py --preset software-requests
```

The preset searches phrases such as:

```text
"looking for" app
"is there an app"
"alternative to"
"wish there was"
"need a tool"
"looking for software"
```

---

## Filter weak intent

Only keep items with at least a chosen intent score:

```bash
python demandradar.py \
  --query "photo manager" \
  --min-intent 3
```

---

## Save a search

```bash
python demandradar.py \
  --query "photo manager" \
  --query "Google Photos alternative" \
  --save-search photos
```

Saved-search configuration is stored under `data/saved_searches.json`.

Run it again later:

```bash
python demandradar.py --run-saved photos
```

List saved searches:

```bash
python demandradar.py --list-saved
```

---

## Monitor a saved search

Run once:

```bash
python monitor.py --search photos
```

Run every 60 minutes and retain the most recent 90 snapshots:

```bash
python monitor.py --search photos --interval-minutes 60 --keep 90
```

Show monitoring history:

```bash
python monitor.py --search photos --history
```

---

## Zero-network demo

Use the bundled synthetic examples to test the pipeline without making web requests:

```bash
python demandradar.py --demo
```

or test watch mode:

```bash
python monitor.py --search demo --demo
```

This is useful for smoke testing, CI and understanding the output format.

---

## Compare against a previous snapshot

```bash
python demandradar.py \
  --query "photo manager" \
  --previous data/old-results.json \
  --out data/new-results.json
```

The resulting opportunity records include trend information when a sufficiently similar older cluster is found.

---

## CSV export

```bash
python demandradar.py \
  --query "shared budget" \
  --csv data/opportunities.csv
```

The CSV includes fields such as topic, mentions, engagement, sources, demand intent, freshness, opportunity score and trend delta.

---

## Local dashboard

Generate or choose a JSON result file, then run:

```bash
python dashboard.py data/results.json
```

Open:

```text
http://127.0.0.1:8765
```

The dashboard server binds only to `127.0.0.1` in the current implementation.

---

## Example output

A simplified opportunity record looks like this:

```json
{
  "topic": "shared budget couples",
  "mentions": 18,
  "engagement": 640,
  "sources": ["reddit", "hn", "github"],
  "demand_intent": 8.2,
  "freshness": 0.91,
  "opportunity_score": 82.4,
  "trend": {
    "state": "rising",
    "previous_score": 65.8,
    "score_delta": 16.6,
    "mentions_delta": 6
  }
}
```

Actual results depend on the selected queries, public source availability and rate limits.

---

## GitHub API token

DemandRadar can search public GitHub Issues without a token, but authenticated requests usually have higher API limits.

PowerShell:

```powershell
$env:GITHUB_TOKEN = "your_token_here"
python demandradar.py --query "need a tool"
```

Bash:

```bash
export GITHUB_TOKEN="your_token_here"
python demandradar.py --query "need a tool"
```

Do not commit tokens to the repository.

---

## Privacy

DemandRadar is designed as a local research tool.

- No DemandRadar account is required.
- No analytics SDK is included.
- No hosted DemandRadar backend is required.
- Search results and monitoring history are stored locally.
- The project does not send collected data to an AI provider.

Live searches still contact the selected public source APIs/endpoints, because that is where the public data comes from.

---

## Current limitations

DemandRadar is intentionally still a young project. Current limitations include:

- Reddit public search can be rate-limited or change behavior.
- Clustering is lexical/vector based rather than embedding or LLM based.
- Similar concepts that use very different vocabulary can end up in separate clusters.
- Competition analysis is not yet part of the opportunity score.
- Reddit comments are not deeply mined yet.
- Alerts are currently local JSONL records rather than email/Telegram/Discord notifications.
- The local dashboard is functional but still minimal.

These limitations are important when interpreting opportunity scores: DemandRadar is a research aid, not a guarantee that a software idea will succeed.

---

## Roadmap

High-value next steps include:

- subreddit-targeted research;
- deeper Reddit comment mining;
- automatic query expansion;
- spam and promotion filtering;
- semantic/embedding clustering as an optional layer;
- competitor discovery and competition scoring;
- demand-vs-competition opportunity ranking;
- daily and weekly trend charts;
- email / Telegram / Discord alerts;
- richer browser dashboard;
- additional public sources where practical;
- packaged installation through `pipx` / PyPI.

---

## Project structure

```text
demandradar.py   Core collectors, intent analysis, clustering, ranking and exports
monitor.py       Saved-search watch runner, snapshots, history and persistent alerts
dashboard.py     Small local HTTP dashboard server
web/             Dashboard frontend
data/            Saved searches and runtime output
 tests/           Automated tests
```

---

## Development

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and [SECURITY.md](SECURITY.md) for security reporting.

---

## License

MIT License. See [LICENSE](LICENSE).
