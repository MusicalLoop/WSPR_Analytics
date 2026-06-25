# WSPR Analytics — Dashboard Design

## Overview

This document captures the agreed design decisions for the WSPR Analytics
dashboard redesign. It serves as the reference for development and should
be updated if decisions change.

**Status:** Built and deployed  
**Branch:** main

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
- TX QTH from configurable lat/lon in config file
- Each receiver plotted as a clickable marker
- Great circle lines from QTH to each receiver
- Distance rings at 500km, 1000km, 1500km
- Marker click shows: callsign, distance, SNR, grid square, country

**Design notes:**

- Map is screen-only — no export for now
- Folium HTML embedded in tab via direct embed (not iframe) —
  `GroupedLayerControl` silently fails to initialise inside an
  iframe's isolated JS context, so the map's header/body/script
  are extracted from Folium and injected directly into the page
- **Known limitation:** the map is built eagerly on every
  `/dashboard` request (including the country lookup via
  pyhamtools), regardless of whether the user ever opens the
  Map tab. The originally planned lazy-load-on-click behaviour
  was not implemented.

---

## Map Tab — Future Enhancements

Three planned improvements, in priority order.

### COMPLETED — Distance layer groups (commit 2228962)

- Group map markers and lines into three Folium FeatureGroups
  matching existing colour scheme: Under 500km, 500-1000km,
  Over 1000km
- Implemented via `folium.plugins.GroupedLayerControl` (not
  `folium.LayerControl` — see Architecture Decisions)
- All layers visible by default
- Allows user to isolate DX contacts by hiding near-field stations

### COMPLETED — Country layer groups (commit 2228962)

- Additional Folium FeatureGroups grouped by country
- Combined with distance layers in the same `GroupedLayerControl` panel
- Allows isolation of specific countries for contest analysis

### MEDIUM TERM — Time-based animation (still planned)

- JavaScript time slider to scrub through the period
- Shows propagation paths appearing/disappearing over time
- Reveals daily propagation cycles, grey line effects,
  band openings
- Implementation: TimestampedGeoJson or custom JS layer filtering
- High visual impact for community sharing

---

### Tab 3 — Charts

**Purpose:** Visual analysis of propagation data.

**Technology:** Chart.js via CDN — no Python dependency, renders in browser
from JSON data passed from Flask.

**Content — six charts in a 2x3 grid:**

| Position | Chart | Data source |
|----------|-------|-------------|
| Top left | Spot count by distance band (bar) | frequencyBinning |
| Top right | SNR vs distance (scatter) | raw spots data |
| Middle left | Spots over time (bar per TX window) | raw spots data |
| Middle right | Country distribution (horizontal bar) | getCountries |
| Bottom left | Azimuth Polar Rose — spot count by compass sector (radar) | raw spots data (azimuth) |
| Bottom right | Propagation over Time — spots (bar) + mean SNR (line), dual axis | hourlyList + raw spots data |

**Design notes:**

- Static appearance but Chart.js provides hover tooltips
- Consistent colour scheme across all charts
- Chart titles and axis labels in plain English

---

### Tab 4 — Analysis

**Purpose:** Detailed tabular analysis for technical users.

**Content — six tables in a 2x3 grid:**

- Hourly distance table (Time, Mean, Min, Max, Spots)
- Top callsigns table (Call Sign, Count, Grid, Distance)
- Furthest stations table (Call Sign, Grid, Distance, Count, Best SNR, Mean SNR)
- Countries table (Country, Spots)
- Best Ears table (Call Sign, Distance, Spots, Mean SNR, Best SNR, Worst SNR) —
  stations consistently decoding the weakest signals (min 3 spots), ranked by mean SNR
- Most Reliable Paths table (Call Sign, Distance, Spots, Mean SNR, Best SNR,
  Worst SNR, Range) — most consistent signal paths (min 3 spots), ranked by SNR range

**Design notes:**

- Existing analysis page content migrated here unchanged
- Tables remain the primary format — no conversion to charts needed
- This tab is for operators who want detail behind the visual story
- Frequency binning and logarithmic binning tables were dropped —
  too technical for most users and already represented visually in
  the Charts tab (Spot Count by Distance Band)

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

**Status: NOT YET IMPLEMENTED.** No Pillow dependency, route, or
template code exists for this feature. The design below is kept
as a reference spec for when it is built.

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

### Bootstrap conflict (Folium)

- Folium injects its own Bootstrap 5.2.2 CSS/JS into the map's
  generated header, which conflicts with the page's own
  Bootstrap 5.3.3 (loaded via base.html)
- Fixed by stripping Folium's Bootstrap `<link>`/`<script>` tags
  from `map_header_html` via regex in app.py before injecting it
  into `{% block head %}`

### Map sizing

- Map wrapper div uses `height: calc(100vh - 180px)` so the map
  fills available vertical space (180px accounts for navbar +
  tab bar + footer)
- The Folium-generated `.folium-map` div is forced to
  `height: 100% !important; width: 100% !important` so it
  inherits that calculated height

### GroupedLayerControl configuration

- `exclusive_groups=False` is required — the default (`True`)
  makes the plugin force-hide every layer in a group except the
  first one at initialisation (radio-button behaviour), which
  contradicts the "all layers visible by default" requirement
- With `exclusive_groups=False`, all layers render as independent
  checkboxes and respect their own `show=True` setting

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

These items were discussed and deliberately deferred. Note:
**Stations tab** and **Map export** are tracked in
`ROADMAP.md`'s Backlog instead — they are genuinely planned,
not abandoned, so they're not listed here.

| Item | Reason parked |
|------|--------------|
| Docker | Overkill for personal tool on stable workstation |
| MQTT / HA integration | Solution looking for a problem for this use case |
| History / comparison | Outside original scope |
| Interactive charts (Plotly) | Static sufficient for now |
| Band filtering | Single band TX, not relevant |
| RX mode analysis | Not the purpose of this tool |
| Scheduled auto-fetch | Manual on-demand fetch suits use case |
