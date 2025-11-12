# Tracking Data Structure Explanation

## Overview

The `tracking_data.json` file contains **all tracking data collected during a session**, including both **bridge events** and **mouse tracking events**. They are **NOT stored separately** - they are all mixed together in a single chronological array.

## File Structure

### Location
```
{project_path}/tracking_data/{session_id}/tracking_data.json
```

### Content Structure

The file is a JSON array containing objects with different `event_type` fields. Each object represents a single tracking event with a timestamp.

## Event Types in tracking_data.json

### 1. **Mouse Position Tracking** (Periodic, ~10 FPS)
```json
{
  "timestamp": "2025-11-12T15:38:51.123456",
  "mouse_position": [100, 200],
  "session_id": "20251112_153851_799187"
}
```
- **Frequency**: Every 100ms (10 times per second)
- **Source**: Python-side mouse tracking via `_collect_tracking_data()`
- **Purpose**: Continuous mouse position monitoring

### 2. **Mouse Press Events**
```json
{
  "timestamp": "2025-11-12T15:38:52.456789",
  "mouse_position": [150, 250],
  "event_type": "mouse_press",
  "button": 1,
  "session_id": "20251112_153851_799187"
}
```
- **Source**: Python-side mouse event handlers
- **Trigger**: User clicks mouse button on the webpage view

### 3. **Mouse Release Events**
```json
{
  "timestamp": "2025-11-12T15:38:52.567890",
  "mouse_position": [150, 250],
  "event_type": "mouse_release",
  "button": 1,
  "session_id": "20251112_153851_799187"
}
```
- **Source**: Python-side mouse event handlers
- **Trigger**: User releases mouse button

### 4. **Mouse Move Events**
```json
{
  "timestamp": "2025-11-12T15:38:52.678901",
  "mouse_position": [160, 260],
  "event_type": "mouse_move",
  "session_id": "20251112_153851_799187"
}
```
- **Source**: Python-side mouse event handlers
- **Trigger**: User moves mouse over the webpage view

### 5. **Bridge Events** (from HTML/JavaScript)
```json
{
  "timestamp": "2025-11-12T15:38:53.123456",
  "event_type": "bridge_event",
  "bridge_event_type": "click",
  "bridge_event_data": {
    "x": 100,
    "y": 200,
    "button": "left"
  },
  "session_id": "20251112_153851_799187"
}
```
- **Source**: HTML page via JavaScript bridge (`sendEvent()`)
- **Trigger**: Events sent from JavaScript using `sendEvent(type, data)`
- **Structure**: 
  - `event_type`: Always `"bridge_event"`
  - `bridge_event_type`: The original event type from JavaScript (e.g., "click", "marker", "custom", "page_load")
  - `bridge_event_data`: The data payload from JavaScript

### 6. **LSL Summary** (Added at session end)
```json
{
  "timestamp": "2025-11-12T15:39:00.000000",
  "event_type": "lsl_summary",
  "total_samples": 4,
  "streams": [
    {
      "name": "MadsPipeline_BridgeEvents",
      "type": "Markers",
      "channel_count": 1,
      "source_id": "session_20251112_153851_799187",
      "session_id": "20251112_153851_799187"
    }
  ],
  "session_id": "20251112_153851_799187"
}
```
- **Source**: Added automatically when session ends
- **Purpose**: Summary of LSL recordings (full data is in separate file)

## Complete Example File

```json
[
  {
    "timestamp": "2025-11-12T15:38:51.123456",
    "mouse_position": [100, 200],
    "session_id": "20251112_153851_799187"
  },
  {
    "timestamp": "2025-11-12T15:38:51.223456",
    "mouse_position": [105, 205],
    "session_id": "20251112_153851_799187"
  },
  {
    "timestamp": "2025-11-12T15:38:52.456789",
    "event_type": "bridge_event",
    "bridge_event_type": "page_load",
    "bridge_event_data": {
      "url": "file:///path/to/page.html",
      "timestamp": 1734010732123
    },
    "session_id": "20251112_153851_799187"
  },
  {
    "timestamp": "2025-11-12T15:38:53.123456",
    "event_type": "bridge_event",
    "bridge_event_type": "click",
    "bridge_event_data": {
      "x": 100,
      "y": 200,
      "button": "left"
    },
    "session_id": "20251112_153851_799187"
  },
  {
    "timestamp": "2025-11-12T15:38:54.789012",
    "mouse_position": [150, 250],
    "event_type": "mouse_press",
    "button": 1,
    "session_id": "20251112_153851_799187"
  },
  {
    "timestamp": "2025-11-12T15:39:00.000000",
    "event_type": "lsl_summary",
    "total_samples": 4,
    "streams": [...],
    "session_id": "20251112_153851_799187"
  }
]
```

## Key Points

1. **All events are in one file**: Bridge events and mouse events are stored together in chronological order
2. **Bridge events are identifiable**: Look for `event_type: "bridge_event"` to find bridge events
3. **Original event type preserved**: The JavaScript event type is stored in `bridge_event_type`
4. **Timestamps are synchronized**: All events use the same timestamp format (ISO 8601)
5. **LSL data is separate**: Full LSL stream recordings are in `lsl_recorded_data.json`

## How to Filter Bridge Events

To extract only bridge events from the file:

```python
import json

with open('tracking_data.json', 'r') as f:
    data = json.load(f)

# Filter bridge events
bridge_events = [
    event for event in data 
    if event.get('event_type') == 'bridge_event'
]

# Filter by specific bridge event type
click_events = [
    event for event in data 
    if (event.get('event_type') == 'bridge_event' and 
        event.get('bridge_event_type') == 'click')
]
```

## Relationship to LSL Data

- **tracking_data.json**: Contains bridge events as they were received (Python-side)
- **lsl_recorded_data.json**: Contains the same bridge events as they were streamed to and recorded from LSL

The LSL file contains:
- The exact same bridge events
- LSL timestamps (different from Python timestamps)
- Relative timestamps from session start
- Stream metadata

Both files contain bridge events, but:
- `tracking_data.json` = Direct Python-side recording
- `lsl_recorded_data.json` = LSL stream recording (includes all LSL streams, not just bridge events)

## Summary

**Bridge events are NOT stored separately** - they are mixed with mouse tracking events in `tracking_data.json`. You can identify them by looking for `event_type: "bridge_event"`. The original JavaScript event type and data are preserved in `bridge_event_type` and `bridge_event_data` fields.

