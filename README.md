# DemandRadar

DemandRadar is a privacy-friendly, open-source demand-mining tool that collects public software requests from Reddit, Hacker News and GitHub Issues, deduplicates them, clusters similar requests, tracks changes over time and surfaces demand alerts.

## v0.4.0

- Automatic watch runner for saved searches
- Snapshot history per saved search
- Previous snapshot is connected automatically for trend deltas
- Persistent JSONL alert log for high-score, rising and new high-intent opportunities
- Retention control with `--keep` so old snapshots are pruned safely
- Run once or repeat at a chosen interval with `--interval-minutes`
- History index containing run count, alert count, top topic, top score and collector coverage
- Existing v0.3 ranking, saved-search, trend and alert engine remains compatible

## Quick start

```bash
python demandradar.py --query "photo manager" --query "shared budget" --save-search ideas
python monitor.py --search ideas
python monitor.py --search ideas --interval-minutes 60 --keep 90
python monitor.py --search ideas --history
python dashboard.py data/history/ideas/<snapshot>.json
```

For a zero-network smoke test:

```bash
python monitor.py --search demo --demo
```

History is stored under `data/history/<saved-search>/`; alerts are appended to `data/alerts.jsonl`. Both are ignored by Git by default. Public endpoints can rate-limit requests. Set `GITHUB_TOKEN` to raise GitHub API limits. DemandRadar has no analytics or hosted backend.
