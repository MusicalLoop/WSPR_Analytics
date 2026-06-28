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
| SNR analysis tables | Best Ears and Most Reliable Paths tables in Analysis tab | 0a945b4 (2026-06-25) |
| Distance to call signs, SNR metrics to furthest stations | Enriched Top Call Signs and Furthest Stations tables | ce3f3c4 (2026-06-25) |
| Project-local .venv created | Avoids collision with deployed venv at /opt/wspr-analytics/venv | 2026-06-24 |
| folium added to requirements.txt | | 2026-06-24 |
| redeploy.sh created | Stop/deploy/start Gunicorn in one command | 2026-06-24 |
| deploy.sh fixed to exclude .venv/ | Prevents copying dev venv into deployed app dir | 2026-06-24 |
| Map time animation | Rolling window timelapse with controls, AJAX backend, pulse effect | 99bc3cf |
| Callsign suffix stripping | Improved country resolution for /KE, /RE, -R suffixes | 8447c52 |
| Unknown callsign flagging | Asterisk marker and note in Analysis tables | 8447c52 |

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

## Review Findings — 2026-06-25

Findings from a full design, functionality, and usability review of the
Dashboard redesign and map animation feature. See conversation history
for full detail on each item.

### Critical (bugs or security)

| Issue | Description | Complexity | Fixed |
|-------|-------------|------------|-------|
| qcut crash on short periods | pd.qcut raises ValueError with few distinct distance values — triggered by 10/30 min presets and single-spot datasets | Low | ✓ 7bcd137 |
| URL encoding missing | call_sign not URL-encoded in wspr.live query — injection risk with special characters | Low | ✓ 7bcd137 |
| Session gate missing | /export-data, /logs, /api/spots, /api/dataset-info have no config_saved check unlike other routes | Low | ✓ 7bcd137 |
| Secret key fallback silent | Falls back to hardcoded key with no warning logged if WSPR_SECRET_KEY not set | Low | ✓ 7bcd137 |

### Performance

| Issue | Description | Complexity | Fixed |
|-------|-------------|------------|-------|
| Duplicate country lookup | pyhamtools runs twice per request — once in analyseData(), once in dashboard route | Low | ✓ ebdc03f |
| Double CSV read | data/WSPR_Analytics.csv read twice per request independently | Low | ✓ ebdc03f |
| Animation frame CSV re-parse | Entire CSV re-parsed on every animation frame — lags at high speed on large datasets | Medium | |
| Eager Folium map build | Map built on every /dashboard request even if Map tab never opened | Medium | |

### Usability and Design

| Issue | Description | Complexity | Fixed |
|-------|-------------|------------|-------|
| Dark mode incomplete | Chart.js and Folium/Leaflet not adapted — charts unreadable in dark mode | Medium | |
| No navbar collapse | No hamburger menu below lg breakpoint — mobile nav broken | Low | ✓ 1e47b09 |
| Metric cards not responsive | Five equal-width cards compress badly on mobile | Low | ✓ 1e47b09 |
| Data table not responsive | 18-column table has no .table-responsive wrapper | Low | ✓ 1e47b09 |
| No map colour legend | No explanation of green/orange/red distance coding | Low | ✓ 1e47b09 |
| Dark mode resets tab | Toggling dark mode reloads page and resets to Summary tab | Medium | ✓ 1e47b09 |
| Reset hides nav | Reset button sets show_menu=False unexpectedly | Low | ✓ 1e47b09 |
| Empty animation window | Zero spots in animation window shows nothing — no message | Low | ✓ 1e47b09 |
| Terminology | SNR, DX, Grid, SWL unexplained for non-technical users | Low | |

---

## Backlog

| Item | Description | Priority |
|------|-------------|----------|
| Stations tab | Full receiver list, sortable, consolidated view | Medium |
| Map export | Static map PNG for share card inclusion | Low |
| SNR over time | Line chart showing band opening/closing | Medium |
| Drift analysis | Flag receivers with clock problems | Low |
| Single page flow | Simplified UX for non-technical OARC users | Low |
| TX/RX dual mode | Full TX and RX analysis with combined view — see docs/TXRX_DESIGN.md | High |
| Share card PNG export | Downloadable image for Discord sharing (Pillow) — see DASHBOARD_DESIGN.md | Medium |
| Lazy-load Folium map | Build map only when Map tab first opened | Medium |
| Cache CSV between animation frames | Avoid re-parsing on every frame | Medium |
| QRZ.com integration | Receiver details in map popups and tables | High |

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
