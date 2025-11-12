# HTML Bridge → LSL → Session Recorder Implementation Summary

## ✅ Implementation Complete

The HTML Bridge → LSL → Session Recorder integration has been successfully implemented. Events from HTML pages are now captured via the Python bridge, streamed to LSL, and recorded during sessions.

## What Was Implemented

### 1. Enhanced Bridge Class (`src/madspipeline/madsBridge.py`)
- ✅ Added structured event handling with JSON parsing
- ✅ Added `event_received` signal for LSL streaming
- ✅ Automatic timestamp addition for events
- ✅ Backward compatibility with plain text messages
- ✅ Error handling for malformed messages

### 2. LSL Integration Module (`src/madspipeline/lsl_integration.py`)
- ✅ **LSLBridgeStreamer**: Streams bridge events to LSL
  - Creates LSL stream outlet for bridge events
  - Handles event serialization to JSON
  - Proper stream metadata and identification
- ✅ **LSLRecorder**: Records all LSL streams during sessions
  - Resolves and connects to all available LSL streams
  - Records samples at 100 Hz (10ms intervals)
  - Calculates relative timestamps from session start
  - Saves recorded data to JSON files

### 3. Embedded Webpage Session Integration (`src/madspipeline/main_window.py`)
- ✅ QWebChannel setup in `EmbeddedWebpageSessionWindow`
- ✅ Bridge registration and connection
- ✅ LSL streamer and recorder initialization
- ✅ Bridge event handler that:
  - Adds events to tracking data
  - Streams events to LSL
  - Updates status bar
- ✅ LSL data saving to session tracking directory
- ✅ Proper cleanup on session end

### 4. JavaScript Bridge Client Updates (`docs/code/madsBridge.js`)
- ✅ Enhanced with `sendEvent()` utility function
- ✅ Better error handling and logging
- ✅ Documentation for event types

### 5. Example HTML Page (`docs/code/BridgeExample.html`)
- ✅ Updated with examples of structured events
- ✅ Demonstrates click, marker, and custom events
- ✅ Shows proper bridge initialization

## Architecture Flow

```
HTML Page (JavaScript)
    │
    │ sendEvent(type, data) or sendToPython(message)
    ▼
madsBridge.js (QWebChannel client)
    │
    │ QWebChannel message
    ▼
madsBridge.py (Bridge class)
    │
    │ event_received signal
    ▼
EmbeddedWebpageSessionWindow._handle_bridge_event()
    │
    ├─► tracking_data (session data)
    │
    └─► LSLBridgeStreamer.push_event()
            │
            │ LSL Stream
            ▼
        LSL Network
            │
            │ (recorded by)
            ▼
        LSLRecorder
            │
            │ saved to
            ▼
        tracking_data/lsl_recorded_data.json
```

## Event Format

Events from HTML should follow this structure:

```javascript
{
  type: 'click',  // Event type: 'click', 'marker', 'custom', etc.
  data: {
    x: 100,
    y: 200,
    button: 'left'
  },
  timestamp: Date.now()  // Optional, added by Python if missing
}
```

## Usage in HTML Pages

```html
<!DOCTYPE html>
<html>
<head>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <script src="madsBridge.js"></script>
</head>
<body>
  <script>
    document.addEventListener("DOMContentLoaded", function () {
      // Initialize bridge
      setupBridge(function (msg) {
        console.log("From Python:", msg);
      });

      // Send structured event (will be streamed to LSL)
      sendEvent('click', {
        x: 100,
        y: 200,
        button: 'left'
      });

      // Send marker event
      sendEvent('marker', {
        label: 'User Action',
        description: 'User clicked button',
        category: 'interaction'
      });
    });
  </script>
</body>
</html>
```

## Data Storage

During a session, data is saved to:
- `tracking_data/{session_id}/tracking_data.json` - All tracking data including bridge events
- `tracking_data/{session_id}/lsl_recorded_data.json` - All LSL stream recordings

## Features

1. **Automatic LSL Streaming**: All bridge events are automatically streamed to LSL
2. **Multi-Stream Recording**: Records all available LSL streams (bridge events + hardware devices)
3. **Timestamp Synchronization**: Events have timestamps synchronized with session timeline
4. **Error Handling**: Graceful degradation if LSL is unavailable
5. **Status Feedback**: Status bar shows bridge and LSL status

## Testing

To test the implementation:

1. Create an embedded webpage project
2. Configure it with a local HTML file that includes the bridge
3. Start a new session
4. Send events from the HTML page using `sendEvent()`
5. Check the status bar for "Bridge and LSL initialized successfully"
6. End the session
7. Check `tracking_data/{session_id}/` for:
   - `tracking_data.json` (should contain bridge events)
   - `lsl_recorded_data.json` (should contain LSL recordings)

## Requirements

- `pylsl` must be installed (already in requirements.txt)
- HTML pages must include:
  - `qrc:///qtwebchannel/qwebchannel.js`
  - `madsBridge.js` (or equivalent bridge setup)

## Status

✅ **All implementation tasks completed**
- Bridge enhancement
- LSL streamer
- LSL recorder
- Session integration
- Data persistence
- Documentation updates

The HTML Bridge → LSL → Session Recorder pipeline is now fully functional!

