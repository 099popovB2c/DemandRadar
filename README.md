# DemandRadar

[![CI](https://github.com/099popovB2c/DemandRadar/actions/workflows/ci.yml/badge.svg)](https://github.com/099popovB2c/DemandRadar/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/099popovB2c/DemandRadar)](https://github.com/099popovB2c/DemandRadar/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DemandRadar is a privacy-friendly, open-source demand-mining tool for software ideas.**

It searches public requests on **Reddit, Hacker News and GitHub Issues**, removes duplicates, groups similar requests, scores demand signals, compares results over time and raises alerts when an opportunity becomes unusually strong or starts rising.

The goal is simple:

> Stop guessing what software people want. Find repeated requests, pain points and replacement searches in public conversations, then track whether demand is growing.

DemandRadar runs locally. It has **no hosted backend, no analytics and no paid AI dependency**.

---

## How it works

```text
Reddit + Hacker News + GitHub Issues
                 |
                 v
        Collect public requests
                 |
                 v
      Retry transient API failures
                 |
                 v
          Deduplicate signals
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

Typical signals include:

```text
"Looking for a simple shared budget app for couples"
"Is there an offline Google Photos alternative?"
"I wish there was a simpler PDF editor"
"Need a tool to manage recurring household bills"
"Would pay for a local-first photo organizer"
```

---

## v0.5.0 hardening and refactor

v0.5.0 focuses on maintainability, reliability, security and test coverage.

### Modular architecture

The former monolithic `demandradar.py` has been split into focused modules:

```text
demandradar.py                 CLI + backward-compatible public facade
monitor.py                     Saved-search watch runner
dashboard.py                   Local HTTP dashboard server

demandradar_core/
  constants.py                 Version and shared constants
  http.py                      Retry/backoff and rate-limit handling
  collectors.py                Reddit / Hacker News / GitHub collectors
  analysis.py                  Deduplication, intent, clustering, scoring
  trends.py                    Snapshot comparison and alerts
  storage.py                   JSON persistence and saved searches
  demo.py                      Offline demo data

web/
  index.html                   Dashboard shell
  app.js                       Safe DOM rendering

tests/
  test_rank.py                 Ranking / intent / storage behavior
  test_monitor.py              Snapshot / retention / alert history
  test_http.py                 Retry and rate-limit behavior
  test_collectors.py           Collector normalization and degradation
  test_dashboard_security.py   XSS/security regression guards
```

The old public function names remain available from `demandradar.py`, so existing scripts using functions such as `rank`, `demo`, `collect`, `intent_score`, `add_trends` and `alerts` continue to work.

### HTTP resilience

Live collectors now use bounded retries with exponential backoff for:

- connection errors and timeouts;
- HTTP `408` and `429`;
- transient `5xx` responses;
- GitHub-style `403` rate limits when `X-RateLimit-Remaining: 0`;
- `Retry-After` and `X-RateLimit-Reset` hints.

A failing source/query pair does **not** abort the full research run. The failure is recorded in coverage metadata and the remaining collectors continue.

### Dashboard security

The dashboard no longer builds external data with `innerHTML`.

- Untrusted strings are rendered through `textContent` / DOM nodes.
- External result links allow only `http:` and `https:` protocols.
- Links opened in a new tab use `noopener noreferrer`.
- The server sends a Content Security Policy, `nosniff`, no-referrer and no-store headers.
- The dashboard server binds to `127.0.0.1` by default.
- Inline JavaScript was moved to `web/app.js` so the CSP can restrict scripts to the local origin.

---

## Data sources

| Source | What is searched | Authentication |
| --- | --- | --- |
| Reddit | Public search results | Not required for the current public endpoint |
| Hacker News | Stories through the Algolia HN API | Not required |
| GitHub | Public Issues Search API | Optional `GITHUB_TOKEN` recommended |

DemandRadar records collector coverage, successful source/query pairs and failures in each result file.

---

## Demand intent detection

DemandRadar looks for language that indicates a real need, replacement search, frustration or willingness to pay.

| Signal | Example language | Relative weight |
| --- | --- | ---: |
| Buying intent | `would pay`, `pay for`, `budget for` | 5 |
| Wish / unmet product | `wish there was` | 5 |
| Direct solution request | `is there an app`, `need a tool` | 4 |
| Active search | `looking for` | 3 |
| Replacement search | `alternative to`, `replacement for` | 3 |
| Pain point | `can't find`, `frustrated`, `annoying` | 3 |
| Workaround | `manual`, `spreadsheet`, `workaround` | 1 |

Each collected item receives intent tags and an intent score before clustering.

---

## Clustering

DemandRadar currently uses local lexical vectors rather than an LLM.

1. Title and body text are tokenized.
2. Common stop words are removed.
3. Token-frequency vectors are built.
4. Cosine similarity is measured against existing clusters.
5. Signals above the configured similarity threshold are grouped together.

This keeps the core zero-dependency and private, while leaving room for optional semantic embeddings later.

---

## Opportunity Score

Each cluster receives a `0–100` opportunity score.

Current weighting:

| Component | Weight |
| --- | ---: |
| Frequency | 28% |
| Engagement | 24% |
| Source diversity | 18% |
| Demand intent | 20% |
| Freshness | 10% |

The score is a research heuristic, not a prediction that a product will succeed.

---

## Requirements

- Python 3.10+
- Internet access for live collectors
- No third-party Python packages for the core project

---

## Quick start

```bash
git clone https://github.com/099popovB2c/DemandRadar.git
cd DemandRadar
python demandradar.py --query "photo manager" --query "shared budget"
```

Results are written to:

```text
data/results.json
```

Offline smoke test:

```bash
python demandradar.py --demo
```

Show version:

```bash
python demandradar.py --version
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

## Saved searches and watch mode

Save a search:

```bash
python demandradar.py \
  --query "photo manager" \
  --query "Google Photos alternative" \
  --save-search photos
```

Run it once:

```bash
python monitor.py --search photos
```

Run every 60 minutes and keep the latest 90 snapshots:

```bash
python monitor.py --search photos --interval-minutes 60 --keep 90
```

View history metadata:

```bash
python monitor.py --search photos --history
```

History is stored under:

```text
data/history/<saved-search>/
```

Alerts are appended to:

```text
data/alerts.jsonl
```

---

## Trends and alerts

When a previous snapshot exists, clusters are annotated as:

```text
new
rising
stable
falling
```

Default alert triggers include:

- opportunity score >= `70`;
- score increase >= `10`;
- a new high-intent cluster.

Thresholds can be changed from the CLI.

---

## CSV export

```bash
python demandradar.py --query "need a tool" --csv opportunities.csv
```

---

## Local dashboard

Generate or choose a result file, then run:

```bash
python dashboard.py data/results.json
```

Open:

```text
http://127.0.0.1:8765
```

A different port can be selected with `--port`.

---

## GitHub API token

Public GitHub Issues can be searched without a token, but authenticated requests generally have higher API limits.

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
- Search results and monitoring history stay local.
- The project does not send collected data to an AI provider.

Live searches still contact the selected public source APIs/endpoints because that is where the public data comes from.

---

## Current limitations

- Reddit public search can be rate-limited or change behavior.
- Clustering is lexical/vector based rather than embedding based.
- Similar concepts using very different vocabulary can end up in separate clusters.
- Competition analysis is not yet part of the opportunity score.
- Reddit comments are not deeply mined yet.
- Alerts are local JSONL records rather than email/Telegram/Discord notifications.
- The dashboard is intentionally lightweight.

---

## Roadmap

High-value next steps include:

- subreddit-targeted research;
- deeper Reddit comment mining;
- automatic query expansion;
- spam and promotion filtering;
- optional semantic/embedding clustering;
- competitor discovery and competition scoring;
- demand-vs-competition ranking;
- daily and weekly trend charts;
- email / Telegram / Discord alerts;
- richer browser dashboard;
- packaged installation through `pipx` / PyPI.

---

## Development

Compile and run the test suite:

```bash
python -m compileall -q demandradar.py monitor.py dashboard.py demandradar_core tests
python -m unittest discover -s tests -v
```

CI currently tests Python 3.10 and 3.13.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and [SECURITY.md](SECURITY.md) for security reporting.

---

## License

MIT License. See [LICENSE](LICENSE).
