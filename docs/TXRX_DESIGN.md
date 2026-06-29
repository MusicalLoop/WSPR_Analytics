# WSPR Analytics — TX/RX Dual Mode Design

## Status
Built and deployed on feature/txrx. 
Merged to main: yes.

## Overview
Extends WSPR Analytics to support receive (RX) analysis 
alongside the existing transmit (TX) analysis. Supports 
three modes: TX only (current behaviour), RX only, and 
Both (TX + RX combined). The Both mode is the primary 
new capability — it reveals propagation asymmetry that 
neither TX nor RX data alone can show.

## What Was Built

### Phases completed
- Phase 1: Configuration mode selector (TX/RX/Both)
- Phase 2: getData() dual-mode, WSPR_TX.csv/WSPR_RX.csv
- Phase 3: TX/RX label adaptation throughout dashboard
- Phase 4: Both mode Summary three-column layout,
  normalize_rx_dataframe fix, wspr.live cooldown
- Phase 5: Both mode map with TX/RX/Symmetric layers,
  adaptive distance rings
- Phase 6: Both mode charts with dual TX/RX datasets
- Phase 7: Both mode Analysis combined tables with
  side-by-side columns, sortable headers, TX/RX filters
- Phase 8: Both mode animation with TX/RX/Both 
  dataset selector

### Key implementation decisions
- normalize_rx_dataframe() swaps tx_sign/rx_sign 
  columns so all existing analysis code works 
  correctly for RX data without modification
- wspr.live 5.5s cooldown between TX and RX queries
  in Both mode to avoid rate limiting
- Symmetric paths computed by inner join on callsign
  across TX rx_sign and RX tx_sign lists
- /api/spots dataset parameter: tx/rx/both
  backward compatible (default tx)
- Combined Analysis tables use Option A side-by-side
  columns with sortable headers and TX/RX filters

### Known limitations
- Best Ears and Most Reliable Paths in Both mode
  show TX/RX toggle only — no combined view
  (true combined analysis deferred, see ROADMAP)
- Share card export not yet adapted for RX/Both mode
  (generates TX-style card regardless of mode)
- Both* button in Analysis tab shows TX data
  (placeholder, true combined view is a planned 
  enhancement)

## Background
The tool was originally designed for a single-band TX 
beacon (Pi Zero 2W running WsprryPi). The expanded use 
case is a PropagaPi (Raspberry Pi with FT-817ND) capable 
of both transmitting and receiving WSPR simultaneously. 
The same callsign (2E0IJC) is used for both TX and RX.

## Configuration Page Changes

### Mode selector
Three radio buttons added below the callsign field:
  TX only — current behaviour, queries tx_sign=CALL&rx_sign=%
  RX only — queries tx_sign=%&rx_sign=CALL
  Both    — makes two separate queries, one TX one RX

Default: TX only (preserves existing behaviour for 
existing users and beacon-only setups).

### Callsign fields
TX only / RX only: single callsign field (current).
Both mode: two fields — TX Callsign and RX Callsign — 
defaulting to the same value with a checkbox 
"Same as TX callsign" that links them.
Rationale: allows analysing a different TX callsign 
against your RX callsign (e.g. monitoring a club beacon 
while also receiving).

### Lat/Lon
Unchanged — always represents the user's QTH regardless 
of mode.

## Data Model

### TX dataset
Rows where tx_sign = user callsign.
Each row = one receiver that heard the user's transmission.
rx_sign, rx_lat, rx_lon = the remote receiver.
tx_lat, tx_lon = user's QTH.

### RX dataset  
Rows where rx_sign = user callsign.
Each row = one transmitter the user received.
tx_sign, tx_lat, tx_lon = the remote transmitter.
rx_lat, rx_lon = user's QTH.

### Symmetric paths (Both mode only)
Stations appearing in both datasets — the user both 
transmitted to them AND received from them.
Computed by inner join on TX rx_sign ∩ RX tx_sign.
Represents confirmed two-way propagation paths.

## Dashboard Summary Tab

### TX only / RX only
Metric cards and labels adapt to mode:

| Card | TX only label | RX only label |
|------|--------------|---------------|
| Total Spots | Total Spots | Total Received |
| Unique Stations | Unique Stations | Unique Transmitters |
| Best DX | Best DX (heard you) | Best DX (you heard) |
| Countries | Countries Heard You | Countries You Heard |
| Best SNR | Best SNR received | Best SNR you received |

### Both mode
Three-column layout: TX | RX | Combined
Each column shows the key metrics for that dataset.
Combined column shows: total unique stations across both,
total unique countries across both.

## Map Tab

### TX only / RX only
Existing behaviour for TX only.
RX only: same visual style but lines come inward 
(remote TX → user QTH). Markers represent transmitters 
not receivers.

### Both mode — layer groups
Extends the existing GroupedLayerControl with new groups:

Transmit layer:
  TX spots — filled circles (current style)
  
Receive layer:
  RX spots — hollow circles (unfilled, same colour coding)
  
Combined layer:
  Symmetric paths — gold filled circles, stations 
  appearing in both TX and RX data

Distance layers (unchanged):
  Under 500km / 500-1000km / Over 1000km

All layers visible by default.
Colour coding (green/orange/red) applies to all layers.

### Map legend
A map legend div (position: bottomleft) explains:
  ● Heard you (TX)
  ○ You heard (RX)  
  ● Symmetric path
  Green = under 500km / Orange = 500-1000km / 
  Red = over 1000km

## Charts Tab

### TX only / RX only
Charts adapt labels to mode. No structural change.

### Both mode
Charts show both datasets as separate series:

Spot Count by Distance Band: 
  Two bar series — TX (blue) and RX (teal), grouped.

SNR vs Distance scatter:
  Two point colours — TX (orange) and RX (purple).
  Tooltip identifies which dataset each point belongs to.

Spots over Time:
  Two bar series — TX and RX, grouped or stacked.

Countries Heard:
  Two horizontal bar series — TX and RX countries.
  Reveals which countries heard you vs which you heard.

Propagation Direction (azimuth rose):
  Two overlapping radar datasets — TX bearings and 
  RX bearings. Most insightful chart in Both mode —
  reveals directional asymmetry of propagation.

Propagation over Time dual axis:
  Four series — TX spots, RX spots (bars), 
  TX mean SNR, RX mean SNR (lines).

## Analysis Tab

### TX only / RX only
Tables adapt labels and data source to mode.

### Both mode
Each table card has a mode selector: [TX ▼] [RX] [Both]
Switching changes the table data without page reload.
"Both" combines both datasets where meaningful.

Table label adaptations for RX mode:
  Top Call Signs → Top Transmitters (stations you heard most)
  Furthest Stations → Furthest Received (stations you heard at greatest distance)
  Best Ears → Best Transmitters (strongest signals you received — reflects their TX power and antenna, not your RX capability)
  Most Reliable Paths → Most Reliable Received Paths

## Animation

Both mode extends the existing animation:
  TX and RX are separate Leaflet LayerGroups
  Both animate simultaneously by default
  User can isolate TX or RX via the existing layer control
  Symmetric path markers are always shown when both 
  layers are active

## Flask Backend Changes

### getData() — WSPR_Analytics.py
New parameter: mode ('tx', 'rx', 'both')
TX: existing behaviour
RX: swap tx_sign/rx_sign in query
Both: two calls, returns tuple of (tx_df, rx_df)

### /dashboard route — app.py
Both mode: calls getData() twice, analyseData() twice
Passes tx_ and rx_ prefixed versions of all data 
to the template: tx_summaryData, rx_summaryData etc.
Symmetric paths computed from intersection of datasets.

### /api/spots — app.py
New parameter: dataset ('tx', 'rx', 'both')
Reads from appropriate CSV:
  data/WSPR_TX.csv (TX data)
  data/WSPR_RX.csv (RX data)
Both: merges and returns with a 'dataset' field per spot.

### CSV file naming
Currently: data/WSPR_Analytics.csv (TX only)
New:
  data/WSPR_TX.csv — TX spots
  data/WSPR_RX.csv — RX spots
Backward compatibility: if mode=tx and WSPR_TX.csv 
missing, fall back to WSPR_Analytics.csv.

## Implementation Order
1. Configuration page mode selector
2. getData() dual-mode support + CSV naming
3. TX only / RX only modes (no Both yet)
   — all existing features work in either mode
4. Both mode — Summary three-column layout
5. Both mode — Map layer groups + legend
6. Both mode — Charts dual datasets
7. Both mode — Analysis mode selectors
8. Both mode — Animation dual layers

## Out of Scope (v1)
- Comparing two different callsigns in Both mode 
  (advanced use case, defer)
- RX-only "Best Ears" equivalent metric 
  (not meaningful from RX data — you only see 
  what you decoded, not what you missed)
- Historical comparison between TX and RX sessions
