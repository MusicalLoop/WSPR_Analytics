# WSPR Analytics — Roadmap

## Current Position

**Branch:** feature/dashboard  
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

---

## In Progress

| Item | Description | Branch |
|------|-------------|--------|
| Dashboard redesign | Tabbed dashboard, revised flow, charts, map | feature/dashboard |

### Dashboard redesign scope

- Revised navigation: Configuration, Dashboard, Data, Logs
- Direct to Dashboard flow after Submit
- Four tabs: Summary, Map, Charts, Analysis
- Summary tab with metric cards
- Map tab with Folium interactive map
- Charts tab with Chart.js visualisations
- Analysis tab with existing tables migrated
- Share card PNG export (Pillow)
- Loading indicator on Configuration submit
- Partials template structure
- Data passed directly to template
- WSPR_DEBUG_CSV flag for analysis CSV control
- Deploy script

---

## Backlog

| Item | Description | Priority |
|------|-------------|----------|
| Stations tab | Full receiver list, sortable, consolidated view | Low |
| Map export | Static map PNG for share card inclusion | Low |
| SNR over time | Line chart showing band opening/closing | Medium |
| Azimuth rose | Polar plot of propagation bearings | Medium |
| Drift analysis | Flag receivers with clock problems | Low |
| Single page flow | Simplified UX for non-technical OARC users | Low |

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
