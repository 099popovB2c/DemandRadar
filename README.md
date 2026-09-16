# DemandRadar

DemandRadar is a privacy-friendly, open-source demand-mining tool that collects public software requests from Reddit, Hacker News and GitHub Issues, normalizes them, groups similar requests and ranks opportunities.

## MVP

- Reddit public search connector (no API key required for light use)
- Hacker News Algolia connector
- GitHub Issues search connector (optional `GITHUB_TOKEN` for higher rate limits)
- Keyword templates such as `looking for app`, `alternative to`, `wish there was`
- Opportunity score based on frequency, engagement and competition hints
- JSON/CSV export
- Static HTML dashboard
- Offline fixture mode for tests

## Quick start

```bash
python demandradar.py --demo --out data/demo.json
python demandradar.py --query "photo manager" --sources reddit,hn,github --out data/results.json
python dashboard.py data/results.json
```

Then open `http://127.0.0.1:8765`.

## Notes

Public endpoints can change or rate-limit requests. DemandRadar uses a clear User-Agent and conservative timeouts. Set `GITHUB_TOKEN` to increase GitHub API limits.

## Privacy

No analytics, no tracking and no hosted backend. Collected public posts stay on your machine.
