# DemandRadar

DemandRadar is a privacy-friendly, open-source demand-mining tool that collects public software requests from Reddit, Hacker News and GitHub Issues, deduplicates them, clusters similar requests, tracks changes over time and surfaces demand alerts.

## v0.3.0

- Saved searches (`--save-search`, `--run-saved`, `--list-saved`)
- Trend comparison against a previous result snapshot
- Rising / falling / stable / new opportunity states
- Alert generation for high scores, fast-rising demand and new high-intent clusters
- Source coverage report so failed collectors are visible instead of silently biasing results
- Intent tags: buying, solution request, replacement, pain, workaround, wish
- Newest-first collection from Reddit, Hacker News and GitHub Issues
- JSON and CSV exports now include trend information

## Quick start

```bash
python demandradar.py --demo --out data/demo.json
python demandradar.py --preset software-requests --limit 20 --out data/results.json
python demandradar.py --query "photo manager" --query "shared budget" --save-search ideas
python demandradar.py --run-saved ideas --previous data/yesterday.json --out data/today.json
python demandradar.py --list-saved
python dashboard.py data/today.json
```

Open `http://127.0.0.1:8765`.

Public endpoints can rate-limit requests. Set `GITHUB_TOKEN` to raise GitHub API limits. DemandRadar has no analytics or hosted backend.
