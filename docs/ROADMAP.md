# WSPR Analytics — Roadmap

## Current Position

**Branch:** main  
**Deployed:** /opt/wspr-analytics/ on A7-Mint  
**Repo:** https://github.com/MusicalLoop/WSPR_Analytics

---

## Completed

| Item | Description | Commit |
|------|-------------|--------|
| Initial release | Flask app, data fetch, tabular analysis | 19a7f98 |
| .gitignore | Exclude secrets, runtime files, venv | 8c1faef |
| secret_key | Externalised to WSPR_SECRET_KEY env variable | 8c1faef |
| getCountries() caching | Resolve unique callsigns only, not per-row | 8c1faef |
| python-dotenv | Added to requirements.txt | 8c1faef |
| gunicorn | Added to requirements.txt | 8c1faef |
| Documentation | DASHBOARD_DESIGN, ROADMAP, INSTALL added | TBC |
| Dashboard redesign | Tabbed dashboard, revised flow, summary cards, Folium map, Chart.js charts, analysis tables | 017463e (2026-06-24) |
| Map distance layer groups | Toggle green/orange/red layers via GroupedLayerControl | 2228962 (2026-06-24) |
| Map country layer groups | Toggle by country via GroupedLayerControl | 2228962 (2026-06-24) |
| Azimuth polar rose | Compass-sector chart of spot count by bearing | 7ae6cdc (2026-06-25) |
| Propagation over time (dual-axis) | Spots (bar) + mean SNR (line) per hour | 7ae6cdc (2026-06-25) |

### Dashboard redesign scope

- Revised navigation: Configuration, Dashboard, Data, Logs
- Direct to Dashboard flow after Submit
- Four tabs: Summary, Map, Charts, Analysis
- Summary tab with metric cards
- Map tab with Folium interactive map
- Charts tab with Chart.js visualisations
- Analysis tab with existing tables migrated
- Loading indicator on Configuration submit
- Partials template structure
- Data passed directly to template
- Deploy script

---

## In Progress

| Item | Description | Branch |
|------|-------------|--------|
| None | | |

---

## Backlog

| Item | Description | Priority |
|------|-------------|----------|
| Stations tab | Full receiver list, sortable, consolidated view | Low |
| Map export | Static map PNG for share card inclusion | Low |
| SNR over time | Line chart showing band opening/closing | Medium |
| Drift analysis | Flag receivers with clock problems | Low |
| Single page flow | Simplified UX for non-technical OARC users | Low |
| Map time animation | Scrub through propagation over time | Medium term |

---

## Parked (No Current Plan)

| Item | Reason |
|------|--------|
| Docker | Overkill for personal tool on stable workstation |
| MQTT / HA integration | Solution looking for a problem for this use case |
| History / comparison | Outside original scope |
| Interactive charts (Plotly) | Static sufficient for now |
| Band filtering | Single band TX, not relevant |
| RX mode analysis | Not the purpose of this tool |
| Scheduled auto-fetch | Manual on-demand fetch suits use case |

---

## Known Issues

| Issue | Status |
|-------|--------|
| visualise route is a stub | Resolved by Dashboard redesign |
| getCountries() slow on Pi Zero 2W | Resolved — caching fix and moved to A7-Mint |
| WSPR_Analytics not suitable for Pi Zero 2W | Resolved — moved to A7-Mint |
