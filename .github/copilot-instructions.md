# MadsPipeline AI Coding Agent Instructions

## Project Overview

**MadsPipeline** is a cross-platform Python/Qt6 application for collecting physiological data streams (eyetracking, heart rate, electrodermal activity) during visual stimulus experiments. Data is synchronized via **Lab Streaming Layer (LSL)** and recorded with screen video for multi-modal analysis.

### Core Purpose
- Manage experimental sessions with multiple project types (picture slideshows, videos, webpages, screen recordings)
- Stream real-time data from LSL devices (Tobii, EmotiBit) with synchronized timestamps
- Capture screen video aligned with event markers from HTML bridges
- Enable post-hoc analysis with temporally-synchronized multi-modal data

### Documentation Policy (AI Agents)

- **Do not create new standalone Markdown files** in the repository unless explicitly requested by a human maintainer. Prefer adding or updating sections in `README.md` or `.github/copilot-instructions.md` to avoid documentation sprawl.
- If substantial new documentation is required and a new file is approved, place it under a dedicated docs/ folder and confirm with the repo owner before committing.
- When modifying documentation, summarize the changes in the commit message and update `README.md` when material affects project usage or developer workflows.


---

## Architecture Essentials

### Three-Layer Design

```
┌─ GUI Layer ──────────────────────────────────────────┐
│  main_window.py: Qt6 desktop app, project/session    │
│  - ProjectCreationDialog, EditProjectDialog           │
│  - EmbeddedWebpageSessionWindow (runs HTML + video)   │
│  - Picture/Video/Recording project windows            │
└────────────────────────────────────────────────────────┘
         ↓ signals/slots, project_manager
┌─ Integration Layer ───────────────────────────────────┐
│  lsl_integration.py: Data collection & recording      │
│  - LSLBridgeStreamer: HTML events → LSL stream        │
│  - LSLMouseTrackingStreamer: Mouse position → LSL     │
│  - LSLRecorder: Multi-stream recording with sync      │
│                                                         │
│  screen_recorder.py: Video capture + sync marker      │
│  - Captures window/fullscreen at configured FPS       │
│  - Sends video_recording_started sync event to LSL    │
│                                                         │
│  madsBridge.py: HTML ↔ Python communication           │
│  - QWebChannel bridge for JavaScript → Python events  │
│  - Events timestamped with LSL local_clock()          │
│  - Falls back to wall_clock if LSL unavailable        │
└────────────────────────────────────────────────────────┘
         ↓ files, config
┌─ Data Layer ──────────────────────────────────────────┐
│  models.py: Dataclasses (Project, Session, Configs)   │
│  project_manager.py: Persistence (JSON, directories)  │
│  Recording output: JSON + MP4 video + LSL native      │
└────────────────────────────────────────────────────────┘
```

### Key Files by Responsibility

| File | Role | Know This |
|------|------|-----------|
| `main_window.py` (3700+ lines) | Main GUI, all project types | Qt6 signals/slots, QWebEngineView for HTML, calls _setup_bridge() and _setup_screen_recording() |
| `lsl_integration.py` | LSL streaming + recording | local_clock() is LSL time domain; inlet.time_correction() gives clock offset; all streams saved to JSON |
| `screen_recorder.py` | Video capture + sync | on_recording_started callback sends video_recording_started event; stores lsl_start_time; FPS configurable |
| `models.py` | Data structures | ProjectType enum (4 types), LSLConfig, ScreenRecordingConfig control settings |
| `madsBridge.py` | HTML ↔ Python bridge | event_received signal emits structured events; LSL-timestamped |
| `project_manager.py` | File I/O | Saves/loads projects to tracking_data/{project_id}/sessions/{session_id}/ |

---

## Critical Patterns & Conventions

### 1. LSL Time Synchronization (Phase 1 Complete ✅)
**Status:** Core infrastructure in place; events use LSL `local_clock()` for cross-device alignment.

**Pattern:**
```python
# ✅ CORRECT: Bridge events timestamped with LSL synchronized clock
from pylsl import local_clock

event_data['timestamp'] = local_clock()  # e.g., 671.345 seconds (LSL domain)
event_data['wall_clock'] = datetime.now().isoformat()  # Preserved for reference
```

**Why:** Bridge events must use same time domain as LSL sensor streams (EmotiBit, Tobii) for correlation.

**When changing time-based code:**
- Always use `local_clock()` for events captured during recording
- Wall clock preserved separately if human readability needed
- Session JSON includes `synchronization_info` with clock offsets per sample

### 2. Video & Event Timestamp Alignment (Video Event Sync Guide ✅)
**Status:** Screen recorder sends sync marker event when recording starts.

**Pattern:**
```python
# Screen recorder calls on_recording_started callback with sync event:
{
    'type': 'video_recording_started',
    'lsl_timestamp': 9.8,  # When video actually started recording
    'session_id': '...',
    'wall_clock': '2025-11-18T14:30:22.456789'
}

# During playback analysis, offset = sync_event['lsl_timestamp']
# video_time = event_lsl_timestamp - offset
```

**When building review tools:**
- Events with negative video_time occurred before video started (not on screen)
- Use sync marker to calculate offset; all subsequent events are aligned

### 3. Optional Dependency Pattern
**Used for:** LSL, matplotlib, cv2, OpenCV codecs

**Pattern:**
```python
try:
    from pylsl import local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    local_clock = None

# Later: use LSL_AVAILABLE guard
if LSL_AVAILABLE and local_clock:
    timestamp = local_clock()
else:
    timestamp = datetime.now().isoformat()  # Graceful fallback
```

**Why:** MadsPipeline should work with partial functionality; not all users have all devices.

### 4. Callback Pattern for Cross-Component Communication
**Used in:** ScreenRecorder → bridge event flow

**Example:**
```python
def on_video_recording_started(sync_event):
    """Callback when screen recording starts."""
    if self.lsl_streamer:
        self.lsl_streamer.push_event(sync_event)

# Pass callback during initialization
screen_recorder = ScreenRecorder(
    session_id=session.session_id,
    config=config,
    output_dir=output_dir,
    window=self,
    on_recording_started=on_video_recording_started  # ← callback
)
```

**Why:** Decouples components; screen_recorder doesn't need to know about LSL.

### 5. Project Type Specialization
**Pattern:** Each ProjectType has a dedicated config class + session window class

| Type | Config Class | Session Window | Key Feature |
|------|--------------|----------------|-------------|
| PICTURE_SLIDESHOW | PictureSlideshowConfig | (in main_window) | Auto-advance slides, emit slide_changed markers |
| VIDEO | VideoConfig | (in main_window) | Auto-play, seek to start/end times |
| EMBEDDED_WEBPAGE | EmbeddedWebpageConfig | EmbeddedWebpageSessionWindow | HTML bridge, LSL events, screen recording |
| SCREEN_RECORDING | ScreenRecordingConfig | (in main_window) | Video capture with FPS/resolution, codec fallback |

**When adding a new project type:**
1. Add to ProjectType enum
2. Create Config dataclass in models.py
3. Add to Project.to_dict() serialization
4. Add UI config section in EditProjectDialog._setup_type_config_ui()
5. Create or reuse session window class

---

## Critical Developer Workflows

### Running the Application
```bash
# Activate venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Run (entry point is src/madspipeline/main.py)
python src/madspipeline/main.py
# OR
python run.py

# VS Code launch config: "Launch Main Application" uses the above
```

### Running Tests
```bash
# All tests
python -m pytest tests -v

# Unit only (models, data structures)
python -m pytest tests/unit -v

# Integration only (GUI, LSL, HTML bridge)
python -m pytest tests/integration -v

# Specific test
python -m pytest tests/integration/test_embedded_webpage_session.py::test_page_load -v

# With coverage (pytest-cov)
python -m pytest tests --cov=src/madspipeline --cov-report=html
```

### Code Quality
- **Format:** `black --line-length=88 src/`
- **Lint:** `flake8 src/`
- **Import sort:** `isort src/`
- **Type check:** `mypy src/madspipeline/` (configured strict in pyproject.toml)

All configured in pyproject.toml; VS Code extensions auto-format on save.

### Debugging
- **Launch.json configs:** "Launch Main Application", "Debug Current Test File", "Run All Tests"
- **Console:** Check VS Code Debug Console for [JS-*] console messages forwarded from embedded webpages
- **LSL status:** lsl_manager.py dialog shows available streams and test receiver

---

## Data Flow Examples

### Embedded Webpage Session with Events + Video
```
User clicks "Start Session" with HTML project
  ↓
main_window.EmbeddedWebpageSessionWindow.__init__()
  ├─ self.session_start_time = datetime.now()
  ├─ _setup_ui() → creates web view
  ├─ _setup_bridge() → creates Bridge + LSLBridgeStreamer
  │   └─ LSLRecorder starts recording all streams (wait_time=2.0)
  ├─ _load_webpage() → loads HTML into QWebEngineView
  ├─ _setup_tracking() → mouse tracking timer (10 Hz)
  └─ _setup_screen_recording() → creates ScreenRecorder with callback
      └─ screen_recorder.start_recording()
          ├─ Captures lsl_start_time = local_clock()
          ├─ Creates VideoWriter (MP4 + codec negotiation)
          ├─ Starts capture thread
          └─ Calls on_recording_started() callback
              └─ lsl_streamer.push_event({ type: 'video_recording_started', lsl_timestamp: ... })

HTML page loads, JavaScript runs:
  ├─ Sends 'page_load' event via bridge
  │   └─ Bridge.receiveMessage() → timestamps with local_clock()
  │       └─ Emits event_received signal
  │           └─ main_window._handle_bridge_event() pushes to LSL
  └─ User fills form, selects video on Step 3
      ├─ Sends 'radio_selected' events
      ├─ Sends 'step_change' events
      └─ Video autoplay sends 'video_started' + 'video_completed'

Meanwhile:
  ├─ Screen recorder capture loop (every 33ms @ 30 FPS) encodes frames
  ├─ Mouse tracking timer (every 100ms @ 10 Hz) captures position → LSL
  └─ LSL timer (every 20ms @ 50 Hz) records all LSL streams

User ends session:
  ├─ Sends 'session_end' event from HTML
  └─ main_window._end_session()
      ├─ screen_recorder.stop_recording() → closes MP4 file
      ├─ lsl_recorder.stop_recording() → closes JSON + metadata
      └─ Emit session_ended(session_id) signal

Output files:
  tracking_data/{project_id}/sessions/{session_id}/
  ├─ screen_recording_{session_id}.mp4 (video + all frames)
  ├─ lsl_recording_{session_id}.json (all streams + sync metadata)
  ├─ screen_recording_info_{session_id}.json (video metadata, fps, resolution)
  └─ tracking_data.json (mouse, legacy)
```

### Event Playback Alignment (Analysis Phase)
```
1. Load session JSON + MP4
2. Find sync event: filter events where type == 'video_recording_started'
3. Extract offset = sync_event['lsl_timestamp']  # e.g., 9.8 seconds
4. For each event:
   - video_time = event['lsl_timestamp'] - offset
   - If video_time < 0: event happened before video (not on screen)
   - If video_time >= 0: seek MP4 to video_time, show event marker
```

---

## Common Tasks & Code Locations

| Task | File | Pattern |
|------|------|---------|
| Add a new LSL stream type to record | `lsl_integration.py` LSLRecorder | Create StreamInlet, append to recorded_data in record_sample() |
| Change video codec preference | `screen_recorder.py` start_recording() | Modify codecs_to_try list; H264 preferred for quality |
| Add HTML bridge event type | `madsBridge.py` receiveMessage() | Already handles JSON events; just send from HTML via sendEvent() |
| Adjust screen recording timing | `main_window.py` _setup_screen_recording() | Change on_recording_started callback timing or ScreenRecorder init |
| Change project save location | `project_manager.py` + `models.py` Project class | Modify base path; sessions go to project_path/tracking_data/{project_id}/sessions/{session_id}/ |
| Add GUI option for project type | `main_window.py` ProjectCreationDialog | Add combo box item, handle in _collect_type_config() |

---

## Known Limitations & Workarounds

1. **Screen recording starts slightly after session** → Solved by sync marker event; use offset during playback
2. **Different LSL devices may have clock drift** → Recorded in clock_offset per sample; post-hoc correction possible
3. **HTML iframe isolation** → Use QWebChannel bridge only; external scripts not available
4. **Cross-platform video codec availability** → Fallback chain: H264 → XVID → mp4v; test in start_recording()
5. **Qt6 DPI scaling on Windows** → Handled by ScreenRecorder using Windows API or DPR multiplier

---

## Phase 3 Development Goals (Target: Nov 25, 2025)

### 1. Data Export System (HIGH PRIORITY)

**Current Issue:** Export only includes project metadata, not actual tracking data

**Implementation Targets:**
- `project_manager.py`: Add `export_session_data(session_id, format='json', include_video=False)` method
  - Formats: 'json' (full structure) | 'csv' (flattened tables)
  - Include options: tracking_data, events, mouse, video metadata
  - Sanitization: timestamp normalization, PII filtering if needed

- `main_window.py`: Add export dialogs
  - Session export dialog (single session selector)
  - Project export dialog (all sessions or date range selector)
  - Format selector (JSON, CSV, or both)
  - Preview before export

**Data to include:**
- LSL streams: All recorded streams with timestamps
- Bridge events: All HTML events with sync info
- Mouse tracking: X, Y coordinates with event types
- Video metadata: Resolution, FPS, codec, duration
- Sync markers: video_recording_started with offset

**CSV Column Structure Example:**
```
timestamp,stream_name,channel_index,data_value,clock_offset,event_type
671.234,MadsPipeline_BridgeEvents,0,page_load,0.001,marker
671.345,MadsPipeline_MouseTracking,0,1920,0.002,numeric
671.345,MadsPipeline_MouseTracking,1,1080,0.002,numeric
```

### 2. LSL Stream Synchronization Testing (HIGH PRIORITY)

**Current Issue:** Only mouse tracking tested; hardware streams (EmotiBit, Tobii) untested

**Implementation Targets:**
- `tests/integration/test_lsl_sync.py`: New test module
  - Test LSL clock sync with mock device streams
  - Validate clock_offset calculations
  - Test sync marker accuracy (±10ms tolerance)
  - Test with multiple simultaneous streams

- `lsl_integration.py`: Add sync validation helpers
  ```python
  def validate_stream_sync(stream_name, samples, tolerance_ms=10):
      """Verify samples are chronologically ordered and within tolerance."""
  
  def calculate_clock_drift(samples):
      """Return clock drift statistics for stream."""
  ```

- Documentation: Sync validation procedures
  - Expected offset ranges per device
  - Clock drift acceptable limits
  - Post-hoc correction algorithm

### 3. LSL Stream Management Overhaul (HIGH PRIORITY)

**Current Issue:** Cannot select which channels/types to record per device

**Implementation Targets:**
- `models.py`: Enhance `LSLConfig`
  ```python
  @dataclass
  class StreamProfile:
      stream_name: str
      stream_type: str
      channels_to_record: List[str] = field(default_factory=list)  # [] = all
      enabled: bool = True
  
  @dataclass
  class LSLConfig:
      profiles: List[StreamProfile] = field(default_factory=list)
      # existing fields...
  ```

- `lsl_manager.py`: Redesigned UI
  - Device/stream list showing available channels
  - Checkbox UI for channel selection
  - Preview panel showing what will be recorded
  - "Save Profile" button to persist configuration
  - "Refresh Streams" button (already exists, verify)

- `lsl_integration.py`: Update `LSLRecorder`
  - Respect `channels_to_record` when recording
  - Skip disabled streams
  - Handle empty channel lists (record all)

### 4. Video Playback Alignment Testing (HIGH PRIORITY)

**Current Issue:** Need to verify video resolution matches events and sync markers are accurate

**Implementation Targets:**
- Create test fixture: Generate recording with known events
  - Create 10-second test HTML page
  - Emit events at t=1s, 3s, 5s, 7s
  - Record video at 30 FPS (300 frames total)
  - Verify sync marker, video duration, event alignment

- `tests/integration/test_video_playback_alignment.py`
  - Test video resolution (1920x1080, 1280x720, etc.)
  - Verify video_recording_started event present
  - Calculate offset: `offset = sync_event['lsl_timestamp']`
  - Validate all events: `video_time = event['timestamp'] - offset`
  - Check for negative times (events before recording start)
  - Verify frame count matches video duration

- `screen_recorder.py`: Add playback metadata
  - Store in `get_recording_info()`: frame_count, duration_seconds, expected_frames
  - Validate in test: `frame_count == fps * duration_seconds`

### 5. UI/UX Improvements (MEDIUM PRIORITY)

**Disable Debug Session Button:**
- `main_window.py`: Find debug session button creation
- Add `button.setEnabled(False)` or hide button
- Add comment: `# TODO: Re-enable after Phase 3 completion`

**Add "Open Folder in Explorer" Button:**
- `main_window.py`: In project overview/dashboard
- When clicked: `os.startfile(project_path)` (Windows) | `subprocess.Popen(['open', project_path])` (macOS)
- Add tooltip: "Open project folder in file explorer"
- Same for individual sessions: "Open session folder"

### 6. Project File Structure Audit (MEDIUM PRIORITY)

**Current Issue:** Some redundancy in tracking_data structure; confusing layout

**Analysis Checklist:**
- [ ] Compare session data files (duplicates between JSON and legacy formats?)
- [ ] Are video metadata + video file properly linked?
- [ ] Is mouse tracking stored in multiple places?
- [ ] Can we consolidate LSL recordings and bridge events?
- [ ] Should video frames be separate file or in JSON?

**Audit steps:**
1. Create test session, record data
2. Examine `tracking_data/{project_id}/sessions/{session_id}/` directory
3. Document each file's purpose and data
4. Identify redundancies
5. Propose optimized structure
6. Create migration utility if needed

**Likely findings to address:**
- Consolidate `tracking_data.json` + `lsl_recording_{session_id}.json`
- Consider storing video resolution/codec in screen_recording_info.json instead of redundantly
- Flatten directory if too deeply nested

---

## Testing Priorities

- **Unit:** models.py (enum conversions, config dataclasses), project_manager.py persistence
- **Integration:** HTML bridge event flow, LSL stream recording, screen recording sync markers
- **GUI:** Session window lifecycle, project creation/editing dialogs (slower; use GUI markers)

Run: `pytest tests/integration/test_embedded_webpage_session.py` for critical path validation.

---

## Quick Reference: What Changed Recently

**Phase 1 Complete (LSL Sync):**
- madsBridge.py: Events now use local_clock() ✅
- lsl_integration.py: Records clock_offset per sample ✅

**Video Event Sync (Just Added):**
- screen_recorder.py: Added on_recording_started callback ✅
- main_window.py: ScreenRecorder now sends video_recording_started event ✅
- See VIDEO_EVENT_SYNC_GUIDE.md for playback usage ✅

**Phase 3 Goals (Current Sprint - Nov 25 deadline):**
- Data export (CSV/JSON, session/project level)
- LSL sync testing for all device types
- LSL Manager UI overhaul (channel selection)
- Video playback validation
- Minor UI fixes (disable debug, add explorer button)
- Project structure audit & optimization

---

## When You're Stuck

1. **Timeline/timestamp issues** → Check README "Video & Event Timestamp Synchronization" section
2. **LSL stream not appearing** → Run lsl_manager.py dialog "Refresh Streams" + check device connected
3. **Video not aligning with events** → Verify video_recording_started event was sent; check sync marker in JSON
4. **HTML bridge events not firing** → Check madsBridge.js loaded + bridge.receiveMessage callable from JS
5. **Project won't load** → Check project_manager.py JSON deserialization + Project.from_dict()
6. **Export not working** → Check project_manager.py has export_session_data() method; verify format parameter

**Debug level:** Run with `--verbose` flag or add print statements; all output visible in VS Code Debug Console.
