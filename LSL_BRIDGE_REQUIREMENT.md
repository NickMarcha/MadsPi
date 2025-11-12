# HTML Bridge → LSL → Session Recorder Integration Requirement

## Overview

This document describes the **critical missing feature** for embedded webpage sessions: events captured from HTML pages via the Python bridge must be streamed to LSL (Lab Streaming Layer) and then recorded by the session recorder.

## Current State

### What Exists:
1. ✅ **Basic Bridge (`madsBridge.py`)** - Simple QObject with signal/slot for communication
2. ✅ **JavaScript Bridge Client (`madsBridge.js`)** - Client-side bridge setup
3. ✅ **Embedded Webpage Session Window** - Can display webpages
4. ✅ **pylsl dependency** - Listed in requirements.txt
5. ✅ **Basic tracking data collection** - Mouse events collected directly

### What's Missing:
1. ❌ **Bridge integration in EmbeddedWebpageSessionWindow** - Bridge is not set up
2. ❌ **QWebChannel setup** - No channel created to connect JS and Python
3. ❌ **LSL stream outlet for bridge events** - No LSL streaming
4. ❌ **LSL stream recording** - No recording of LSL streams during sessions
5. ❌ **Event flow pipeline** - HTML events don't reach LSL or session recorder

## Required Architecture

```
┌─────────────────┐
│   HTML Page     │
│  (JavaScript)   │
└────────┬────────┘
         │ sendToPython(event)
         ▼
┌─────────────────┐
│  madsBridge.js   │
│  (QWebChannel)  │
└────────┬────────┘
         │ QWebChannel message
         ▼
┌─────────────────┐
│  madsBridge.py  │
│  (Bridge class) │
└────────┬────────┘
         │ receiveMessage(event)
         ▼
┌─────────────────┐
│  LSL Stream     │
│  (pylsl)        │
│  StreamOutlet   │
└────────┬────────┘
         │ push_sample(event_data)
         ▼
┌─────────────────┐
│ Session Recorder│
│ (LSL Inlet)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Session Data    │
│ (tracking_data) │
└─────────────────┘
```

## Implementation Requirements

### 1. Bridge Integration in EmbeddedWebpageSessionWindow

**Location:** `src/madspipeline/main_window.py` - `EmbeddedWebpageSessionWindow` class

**Required Changes:**
- Import QWebChannel and Bridge
- Create QWebChannel instance
- Register Bridge object with channel
- Set channel on QWebEngineView
- Connect bridge signals to LSL streaming

**Example:**
```python
from PySide6.QtWebChannel import QWebChannel
from .madsBridge import Bridge

class EmbeddedWebpageSessionWindow(QMainWindow):
    def __init__(self, ...):
        # ... existing code ...
        
        # Set up bridge and QWebChannel
        self.bridge = Bridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        # Connect bridge to LSL
        self.bridge.message_received.connect(self._handle_bridge_event)
```

### 2. Enhanced Bridge Class

**Location:** `src/madspipeline/madsBridge.py`

**Required Changes:**
- Add signal for structured events (not just strings)
- Support event types (clicks, markers, custom events)
- Add timestamp handling
- Validate incoming messages

**Example:**
```python
class Bridge(QObject):
    # Signal for structured events
    event_received = Signal(dict)  # {type, data, timestamp}
    
    @Slot(str)
    def receiveMessage(self, msg: str):
        try:
            event_data = json.loads(msg)
            # Validate event structure
            if 'type' in event_data and 'data' in event_data:
                event_data['timestamp'] = datetime.now().isoformat()
                self.event_received.emit(event_data)
        except json.JSONDecodeError:
            # Handle non-JSON messages
            pass
```

### 3. LSL Stream Outlet

**Location:** New file or in `EmbeddedWebpageSessionWindow`

**Required Changes:**
- Create LSL StreamInfo for bridge events
- Create StreamOutlet
- Push events to LSL stream in real-time
- Handle stream lifecycle (start/stop with session)

**Example:**
```python
from pylsl import StreamInfo, StreamOutlet

class LSLBridgeStreamer:
    def __init__(self, session_id: str):
        # Create LSL stream for bridge events
        info = StreamInfo(
            name='MadsPipeline_BridgeEvents',
            type='Markers',
            channel_count=1,
            nominal_srate=0,  # Irregular rate
            channel_format='string',
            source_id=f'session_{session_id}'
        )
        self.outlet = StreamOutlet(info)
    
    def push_event(self, event_data: dict):
        # Push event to LSL stream
        event_str = json.dumps(event_data)
        self.outlet.push_sample([event_str])
```

### 4. LSL Stream Recording

**Location:** `EmbeddedWebpageSessionWindow` or new `LSLRecorder` class

**Required Changes:**
- Create LSL StreamInlet to receive streams
- Record stream data during session
- Save recorded data to session tracking_data
- Synchronize timestamps with session timeline

**Example:**
```python
from pylsl import StreamInlet, resolve_streams

class LSLRecorder:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.recorded_data = []
        self.inlets = []
        
    def start_recording(self):
        # Resolve all LSL streams
        streams = resolve_streams()
        for stream in streams:
            inlet = StreamInlet(stream)
            self.inlets.append(inlet)
    
    def record_sample(self):
        # Pull samples from all inlets
        for inlet in self.inlets:
            sample, timestamp = inlet.pull_sample(timeout=0.0)
            if sample:
                self.recorded_data.append({
                    'timestamp': timestamp,
                    'data': sample,
                    'session_id': self.session_id
                })
    
    def save_to_session(self, session: Session):
        # Save recorded LSL data to session
        # ...
```

### 5. Integration Flow

**In EmbeddedWebpageSessionWindow:**

```python
def _setup_tracking(self):
    # ... existing tracking setup ...
    
    # Set up LSL streaming
    self.lsl_streamer = LSLBridgeStreamer(self.session.session_id)
    self.lsl_recorder = LSLRecorder(self.session.session_id)
    self.lsl_recorder.start_recording()
    
    # Connect bridge to LSL
    self.bridge.event_received.connect(self._stream_to_lsl)
    
    # Start LSL recording timer
    self.lsl_timer = QTimer()
    self.lsl_timer.timeout.connect(self.lsl_recorder.record_sample)
    self.lsl_timer.start(10)  # 100 Hz

def _stream_to_lsl(self, event_data: dict):
    """Stream bridge event to LSL."""
    self.lsl_streamer.push_event(event_data)

def _end_session(self):
    # ... existing code ...
    
    # Save LSL recorded data
    lsl_data = self.lsl_recorder.recorded_data
    # Save to session tracking_data
    # ...
```

## Event Format

Events from HTML should follow this structure:

```javascript
// In HTML/JavaScript
sendToPython(JSON.stringify({
    type: 'click',  // or 'marker', 'custom', etc.
    data: {
        x: 100,
        y: 200,
        button: 'left'
    },
    timestamp: Date.now()  // Optional, will be added by Python
}));
```

## Testing Requirements

1. **Unit Tests:**
   - Bridge message parsing
   - LSL stream creation
   - Event validation

2. **Integration Tests:**
   - HTML → Bridge → LSL flow
   - LSL recording during session
   - Data persistence

3. **Manual Testing:**
   - Load HTML page with bridge
   - Send events from JavaScript
   - Verify LSL stream exists
   - Verify events recorded in session

## Priority

**🔴 CRITICAL** - This is a core requirement for embedded webpage sessions. Without this, events from HTML pages cannot be captured and recorded, which defeats the purpose of embedded webpage sessions.

## Related Files

- `src/madspipeline/madsBridge.py` - Bridge class (needs enhancement)
- `src/madspipeline/main_window.py` - EmbeddedWebpageSessionWindow (needs integration)
- `docs/code/madsBridge.js` - JavaScript bridge client (may need updates)
- `requirements.txt` - pylsl already listed

## Next Steps

1. Enhance Bridge class with structured event handling
2. Integrate QWebChannel in EmbeddedWebpageSessionWindow
3. Implement LSL stream outlet for bridge events
4. Implement LSL stream recording
5. Test end-to-end flow
6. Update documentation

