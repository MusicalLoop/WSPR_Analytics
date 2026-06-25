# WSPR Analytics — Map Time Animation

## Status
Built and deployed. Branch: main

## Overview
A timelapse animation of WSPR propagation paths over time.
The user watches propagation paths appear and disappear as 
the selected time window moves through the dataset.
The animation replaces the static map view — both cannot 
be active simultaneously.

## Minimum Period Gating

| Period | Behaviour |
|--------|-----------|
| Under 3 hours | Hard block — animation controls not shown, muted message: "Select 3 hours or more to enable time animation" |
| 3–6 hours | Soft warning — animation available but a banner says "Time animation works best with 6+ hours of data" |
| 6 hours and above | Fully enabled, no warning |

Period is determined from the dataset time range, not the 
config setting — uses actual min/max timestamps in the data.

## Animation Modes

### Rolling Window (default)
Shows all spots within a moving time window centred on the 
current position. As time advances, old spots outside the 
window drop off and new spots appear.

### Snapshot
Shows only spots from the exact current time slot 
(one TX window = 2 minutes, or the selected granularity).
More precise, more flickery.

## Controls Layout
[▶ Play] [⏸ Pause]   Speed: |──●──|   Mode: [Rolling ▼]   [○ Pulse]

Window:  |──●──────────|  2 hours

15m  1h  2h  6h  12h

14 Jun 08:00 ──────●─────────── 17 Jun 21:00

Current: 15 Jun 14:00–16:00

### Control descriptions

**Play/Pause:** Starts/stops automatic time advancement.
Keyboard shortcut: spacebar.

**Speed:** Slider controlling frames per second.
Range: 0.5x (slow) to 8x (fast). Default: 2x.
One "frame" = advancing time by the granularity step.

**Mode selector:** Rolling Window or Snapshot.
Changing mode redraws current frame immediately.

**Pulse toggle:** Checkbox. Default OFF.
When ON, animation markers have a CSS pulse effect.
When OFF, markers are clean static circles.

**Window size slider:** Only visible in Rolling Window mode.
Adaptive discrete steps based on total dataset period:
- Under 12 hours: 15min, 30min, 1hr, 2hr
- 12hrs–3 days: 1hr, 2hr, 4hr, 6hr, 12hr
- 3 days–14 days: 2hr, 6hr, 12hr, 1day

**Time position slider:** Always visible.
Dragging moves to any point in the dataset.
Auto-advances during Play.
Loops back to start when it reaches the end.

**Timestamp overlay:** Displayed top-left of the map.
Format: "15 Jun 14:00 – 16:00" (rolling window)
or "15 Jun 14:02" (snapshot).
Implemented as a Leaflet custom control.

## Static vs Animation Mode

A button below the map tab heading switches modes:
"Switch to Animation" / "Switch to Static View"

### Static mode (default)
- Existing GroupedLayerControl markers visible
- Existing distance rings visible
- Layer control panel visible (collapsed by default)
- Animation controls hidden

### Animation mode
- Static markers hidden (GroupedLayerControl layers 
  all set to invisible)
- Distance rings remain visible (always)
- Layer control panel hidden
- Animation controls visible
- Animation layer (dynamic markers + lines) shown

Switching back to Static mode:
- Restores all GroupedLayerControl layers to visible
- Hides animation layer
- Shows layer control panel

## Animation Markers

- Colour: same green/orange/red distance coding as static
  (green < 500km, orange 500–1000km, red > 1000km)
- Size: radius 8 (vs static radius 6)
- Lines: PolyLine from TX QTH to each receiver
- Line colour: matches marker colour
- Pulse effect (when enabled): CSS @keyframes animation
  scaling marker from 1x to 1.5x and back, 1.5s cycle

## Flask API Endpoint

### Route
GET /api/spots

### Parameters
- start: ISO datetime string (UTC) — window start
- window: integer minutes — window duration
- mode: "rolling" or "snapshot"

### Response
JSON object:
{
  "spots": [
    {
      "rx_sign": "G4HZX",
      "rx_lat": 51.438,
      "rx_lon": -0.042,
      "distance": 411,
      "snr": -5,
      "time": "14:32"
    },
    ...
  ],
  "window_start": "2026-06-25T14:00:00",
  "window_end": "2026-06-25T16:00:00",
  "total_spots": 23
}

### Error responses
- 400: missing or invalid parameters
- 404: no data file found
- 200 with empty spots array: valid window but no spots

### Data source
Reads from data/WSPR_Analytics.csv (already on disk 
after a dashboard query). Filters by time window.
Uses session to confirm config_saved.

## Granularity

The time position slider advances by one granularity step 
per frame during Play. Granularity is auto-suggested based 
on dataset period but not user-selectable in v1:

| Dataset period | Granularity |
|---------------|-------------|
| Under 6 hours | 15 minutes |
| 6–24 hours | 30 minutes |
| 1–3 days | 1 hour |
| 3–14 days | 4 hours |

## Frontend State

The animation maintains these JavaScript state variables:
- isPlaying: bool
- currentTime: Date object
- datasetStart: Date object  
- datasetEnd: Date object
- windowMinutes: int
- mode: "rolling" or "snapshot"
- speed: float (frames per second)
- pulseEnabled: bool
- animationLayerGroup: Leaflet LayerGroup

## TX QTH
Read from the map's existing TX QTH coordinates 
(already embedded in the page from the dashboard route).
Pass as data attributes on the animation container div:
data-tx-lat and data-tx-lon.

## Implementation Order
1. Backend: /api/spots route (Prompt 1)
2. Frontend: animation controls + JS (Prompt 2)
