# WSPR Analytics — Dashboard Design

## Overview

This document captures the agreed design decisions for the WSPR Analytics
dashboard redesign. It serves as the reference for development and should
be updated if decisions change.

**Status:** Agreed — ready for development  
**Branch:** feature/dashboard

---

## Navigation Structure

```
Configuration | Dashboard | Data | Logs
```

### Page responsibilities

| Page | Purpose |
|------|---------|
| Configuration | Enter callsign, select time period, submit |
| Dashboard | All analysis and visualisation (tabbed) |
| Data | Raw data table, CSV export |
| Logs | Application log viewer |

---

## User Flow

### Primary flow

1. User enters callsign and period on Configuration page
2. Clicks Submit
3. App fetches data from wspr.live
4. App runs full analysis in one step
5. Redirects directly to Dashboard (Summary tab)

### Secondary flow

1. User clicks Data in nav
2. Raw data table shown
3. User clicks Export CSV for contest submission

### Key principle

The Dashboard is the primary destination after submitting. The Data page
is an optional detour, not a mandatory step. This reflects the actual use
case — users want to see results, not raw data.

---

## Dashboard Page

### Tab structure

```
[ Summary ] [ Map ] [ Charts ] [ Analysis ]
```

All tabs are client-side Bootstrap tabs. All data is loaded in a single
request when the Dashboard route is hit. No reloading between tabs.

---

### Tab 1 — Summary

**Purpose:** Headline results at a glance. First tab, default view.

**Content:**

- Five metric cards across the top:
  - Total Spots
  - Unique Stations
  - Best DX (callsign + distance)
  - Countries Heard
  - Best SNR (callsign + SNR value)
- Session details below cards: callsign, band, period covered, TX power
- Share Card export button (generates PNG for Discord sharing)

**Design notes:**

- Cards should be large and readable — contest participants want instant results
- Best DX and Best SNR are the headline contest metrics
- Share card button prominent but not the primary focus

---

### Tab 2 — Map

**Purpose:** Geographic view of propagation paths.

**Content:**

- Folium interactive map
- TX QTH marked at IO95fa (Newcastle)
- Each receiver plotted as a clickable marker
- Great circle lines from QTH to each receiver
- Distance rings at 500km, 1000km, 1500km
- Marker click shows: callsign, distance, SNR, grid square, country

**Design notes:**

- Map is screen-only — no export for now
- Folium HTML embedded in tab via iframe or direct embed
- Only renders when Map tab is clicked (lazy load) to avoid slowing initial Dashboard load

---

### Tab 3 — Charts

**Purpose:** Visual analysis of propagation data.

**Technology:** Chart.js via CDN — no Python dependency, renders in browser
from JSON data passed from Flask.

**Content — four charts in a 2x2 grid:**

| Position | Chart | Data source |
|----------|-------|-------------|
| Top left | Spot count by distance band (bar) | frequencyBinning |
| Top right | SNR vs distance (scatter) | raw spots data |
| Bottom left | Spots over time (bar per TX window) | raw spots data |
| Bottom right | Country distribution (horizontal bar) | getCountries |

**Design notes:**

- Static appearance but Chart.js provides hover tooltips
- Consistent colour scheme across all charts
- Chart titles and axis labels in plain English

---

### Tab 4 — Analysis

**Purpose:** Detailed tabular analysis for technical users.

**Content:**

- Hourly distance table (Time, Mean, Min, Max, Spots)
- Top callsigns table (Call Sign, Count, Grid)
- Furthest stations table (Call Sign, Distance, Grid, Count)
- Frequency binning table (Distance Range, Number of Spots)
- Logarithmic binning table (Distance Range, Number of Spots)

**Design notes:**

- Existing analysis page content migrated here unchanged
- Tables remain the primary format — no conversion to charts needed
- This tab is for operators who want detail behind the visual story

---

## Data Page

**Purpose:** Raw data access and contest export.

**Content:**

- Summary bar at top: row count, date range covered, callsign
- Raw data table (all columns from wspr.live)
- Export CSV button — downloads WSPR_Analytics.csv

**Design notes:**

- Page is populated from the already-fetched CSV
- No recomputation — reads WSPR_Analytics.csv directly
- Export button serves the file as an attachment

---

## Share Card Export

**Purpose:** Single PNG image suitable for Discord sharing.

**Technology:** Pillow (server-side PNG generation)

**Content layout:**

```
+-------------------------------------+
|  2E0IJC - WSPR Beacon Report        |
|  40m  24 June 2026  30 minutes      |
+------------------+------------------+
|  52              |  14              |
|  Stations        |  Countries       |
+------------------+------------------+
|  Best DX:  CT7AJC  1,722 km         |
|  Best SNR: GM0DHD  +7 dB  158 km    |
+-------------------------------------+
|  Top Countries                      |
|  G  DL  PA  OE  EI                  |
+-------------------------------------+
|  Generated by WSPR Analytics        |
|  github.com/MusicalLoop/WSPR_Analytics|
+-------------------------------------+
```

**Behaviour:** Clicking the Share button triggers a download of the PNG.

---

## Architecture Decisions

### TX QTH location

TX QTH stored as decimal lat/lon in config file.
Configured on the Configuration page.
Used as map centre and propagation path origin.

### Data flow

- Configuration Submit triggers fetch + full analysis in one step
- All computed data passed directly to Dashboard template
- No reading back from analysis CSVs in the application
- WSPR_Analytics.csv retained as the raw data export file

### Analysis CSV files

- Controlled by WSPR_DEBUG_CSV flag in .env
- Default: false (production — no CSVs written except raw data)
- Set to true during development for inspection and debugging

### Template structure

```
templates/
├── base.html              # shared nav, footer, Bootstrap, Chart.js CDN
├── index.html             # configuration page
├── dashboard.html         # tabbed dashboard container
├── data.html              # raw data table + export
├── logs.html              # log viewer
└── partials/
    ├── summary.html       # Summary tab content
    ├── map.html           # Map tab content
    ├── charts.html        # Charts tab content
    └── analysis.html      # Analysis tab content
```

### Development workflow

- Feature branch: feature/dashboard
- Flask dev server during development (auto-reload on file changes)
- Gunicorn for deployed instance at /opt/wspr-analytics/
- Deploy via rsync script

### Loading indicator

- Simple spinner shown on Configuration page when Submit is clicked
- Prevents double-submission
- Reassures user that fetch is in progress

---

## Technology Stack

| Component | Technology | Reason |
|-----------|-----------|--------|
| Web framework | Flask + Gunicorn | Existing, works well |
| Templates | Jinja2 + partials | Existing, add partials for tabs |
| CSS framework | Bootstrap 5 | Existing |
| Tab switching | Bootstrap tabs (client-side) | Already available, no extra JS |
| Charts | Chart.js via CDN | Lightweight, no Python dependency |
| Map | Folium | Interactive HTML map, Python native |
| Share card | Pillow | Server-side PNG generation |
| Data analysis | pandas + numpy | Existing |
| Country lookup | pyhamtools | Existing, caching fix applied |

---

## Out of Scope (Parked)

These items were discussed and deliberately deferred:

| Item | Reason parked |
|------|--------------|
| Stations tab | Low priority, can add later |
| Map export | Complex — Folium is HTML not PNG, defer |
| Docker | Overkill for personal tool on stable workstation |
| MQTT / HA integration | Solution looking for a problem for this use case |
| History / comparison | Outside original scope |
| Interactive charts (Plotly) | Static sufficient for now |
| Band filtering | Single band TX, not relevant |
| RX mode analysis | Not the purpose of this tool |
