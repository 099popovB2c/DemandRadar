# DemandRadar

DemandRadar is a privacy-friendly, open-source demand-mining tool that collects public software requests from Reddit, Hacker News and GitHub Issues, deduplicates them, clusters similar requests and ranks opportunities.

## v0.2.0

- Demand-intent scoring for phrases such as `would pay`, `wish there was`, `need a tool` and `alternative to`
- Freshness, source-diversity, frequency and engagement score components
- URL deduplication and title-weighted clustering
- Multi-query mode and a `software-requests` preset
- Minimum intent filtering
- Evidence excerpts and richer dashboard filters/sorting
- JSON/CSV export

## Quick start

```bash
python demandradar.py --demo --out data/demo.json
python demandradar.py --preset software-requests --limit 20 --out data/results.json
python demandradar.py --query "photo manager" --query "shared budget" --min-intent 2 --out data/results.json
python dashboard.py data/results.json
```

Open `http://127.0.0.1:8765`. Public endpoints can rate-limit requests; `GITHUB_TOKEN` raises GitHub API limits. No analytics or hosted backend are used.
