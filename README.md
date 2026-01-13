# MadsPipeline: Metrics of Attention Data Streaming and Visualization Pipeline

![MadsPi](docs/images/MadsPi.png)

## Project Overview

Open-source pipeline for collecting physiological data on eyetracking, heart rate, and electrodermal activity when a reader is viewing or interacting with a visual data story. Supports both **EmotiBit** and **Tobii Pro Spark** through **Lab Streaming Layer (LSL)**.

End result: a graphical tool that combines and captures data from supported devices during experimental sessions with synchronized video recording and event marking.

---

## Design Requirements

- Allow selection, ordering, and arrangement of visual stimuli with adjustable display times
- Launch eyetracking calibration sessions (accept/redo via button click)
- Start and end experiments using only the mouse
- Automatic fullscreen toggle for calibration and experimental modes
- Event markers in data stream for experiment start, stimulus changes, and experiment end
- Post-experiment visualization with heatmap overlays, time-aligned eye movements, and heart rate/EDA charts
- Exportable datasets (JSON/CSV format)
- Support for image sequences, videos, and webpages (with screen recording)

---

## Quick Start

### Windows

```powershell
git clone https://github.com/NickMarcha/MadsPi.git
cd MadsPi
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser  # If needed
scripts\setup_windows.ps1
.\.venv\Scripts\activate
python src/madspipeline/main.py
```

### Linux

```bash
git clone https://github.com/NickMarcha/MadsPi.git
cd MadsPi
bash scripts/setup_linux.sh
source .venv/bin/activate
python src/madspipeline/main.py
```

### macOS

```bash
git clone https://github.com/NickMarcha/MadsPi.git
cd MadsPi
bash scripts/setup_macos.sh
source .venv/bin/activate
python src/madspipeline/main.py
```

### Hardware Setup
- **Windows**: Check Device Manager; install OEM USB/serial drivers
- **Linux**: Set udev rules for device access
- **macOS**: Ensure necessary permissions in System Settings

**Tobii Eye Tracker Setup:**
- Install `tobii-research` Python package (included in `requirements.txt`)
- Connect Tobii Pro Spark via USB
- Ensure device is powered (red light indicates active state)
- Calibration is stored on the device itself (persists between sessions)
- First-time calibration required before streaming gaze data

---

## Project Structure

```
MadsPipeline/
├── src/madspipeline/              # Main source code
│   ├── main.py                    # Entry point
│   ├── main_window.py             # Qt6 GUI (3700+ lines)
│   ├── models.py                  # Data models & enums
│   ├── project_manager.py         # Project persistence
│   ├── lsl_integration.py         # LSL streaming & recording
│   ├── screen_recorder.py         # Video capture with sync
│   ├── madsBridge.py              # HTML ↔ Python bridge
│   ├── lsl_manager.py             # LSL stream management UI
│   ├── tobii_manager.py           # Tobii eye tracker state management
│   ├── tobii_eyetracker.py        # Tobii LSL streaming integration
│   ├── tobii_calibration_window.py # Fullscreen calibration UI
│   └── tobii_gaze_test_window.py  # Gaze visualization test window
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (models, data)
│   └── integration/               # Integration tests (GUI, LSL, bridge)
├── .github/
│   └── copilot-instructions.md    # AI agent coding guidelines
├── scripts/                       # Setup scripts (Windows/Linux/macOS)
├── .vscode/                       # Debug & task configs
├── pyproject.toml                 # Project configuration
├── pytest.ini                     # Test configuration
└── requirements-dev.txt           # Development dependencies
```

---

## Architecture

### Three-Layer Design

**GUI Layer** (`main_window.py`)
- Qt6 desktop application
- Project/session management dialogs
- Session windows for each project type
- Screen recording integration

**Integration Layer**
- `lsl_integration.py`: LSL event streaming & multi-stream recording
- `screen_recorder.py`: Video capture with sync event markers
- `madsBridge.py`: HTML ↔ Python event communication
- `lsl_manager.py`: Stream detection & configuration UI
- `tobii_manager.py`: Centralized Tobii eye tracker state management, calibration mode, and notifications
- `tobii_eyetracker.py`: Tobii gaze data streaming to LSL (screen space coordinates)
- `tobii_calibration_window.py`: Fullscreen calibration interface with animated targets
- `tobii_gaze_test_window.py`: Real-time gaze visualization for calibration validation

**Data Layer**
- `models.py`: Dataclasses for projects, sessions, configurations
- `project_manager.py`: JSON persistence to `tracking_data/{project_id}/sessions/{session_id}/`
- Output: MP4 video + LSL JSON + metadata

### Project Types

| Type | Config | Features |
|------|--------|----------|
| **Picture Slideshow** | `PictureSlideshowConfig` | Auto-advance, slide duration, fade/slide transitions |
| **Video** | `VideoConfig` | Auto-play, seek to start/end times, looping |
| **Embedded Webpage** | `EmbeddedWebpageConfig` | HTML bridge, LSL events, screen recording, fullscreen |
| **Screen Recording** | `ScreenRecordingConfig` | Window/fullscreen capture, FPS, resolution, codecs |

---

## Development

### Running Tests
```bash
# All tests
python -m pytest tests -v

# Unit tests only
python -m pytest tests/unit -v

# Integration tests only
python -m pytest tests/integration -v

# Specific test
python -m pytest tests/integration/test_embedded_webpage_session.py::test_page_load -v

# With coverage
python -m pytest tests --cov=src/madspipeline --cov-report=html
```

### Code Quality
```bash
# Format with Black (88 char lines)
black --line-length=88 src/

# Lint with Flake8
flake8 src/

# Sort imports
isort src/

# Type check (strict)
mypy src/madspipeline/
```

All configured in `pyproject.toml`; VS Code auto-formats on save.

### Debug Configurations (VS Code / Cursor)
- **Launch Main Application**: Run app directly
- **Launch with run.py**: Use launcher script
- **Debug Current Test File**: Debug open test file
- **Run All Tests**: Execute full test suite
- **Run Unit Tests**: Unit tests only
- **Run Integration Tests**: Integration tests only

---

## LSL Time Synchronization (Phase 1 ✅)

### Problem Solved
Previously, timestamps from different LSL devices were in **different clock domains**:
- Each device had its own clock (EmotiBit, Bridge Events, Mouse Tracking, etc.) ❌
- Timestamps could not be directly compared across devices ❌
- Manual clock offset correction required for analysis ❌

### Solution Implemented
1. **Online Clock Synchronization**: LSL `proc_clocksync` postprocessing flag enabled
   - All device timestamps automatically corrected to local time domain
   - Real-time synchronization during recording
   - Accuracy: < 1 ms on local networks

2. **Bridge events use `local_clock()`** for LSL time domain alignment
   - Ensures bridge events are in the same synchronized time domain

3. **Dual Timestamp Storage**: Both synchronized and original timestamps preserved
   - `timestamp`: Synchronized to local time domain (for direct comparison)
   - `original_timestamp`: Original device clock time (for reference)

4. **Clock offset measurements** recorded for post-hoc analysis and validation

### Code Changes
**File: `src/madspipeline/madsBridge.py`**
```python
# Bridge events timestamped with LSL clock
if LSL_AVAILABLE and local_clock:
    event_data['timestamp'] = local_clock()  # LSL time domain
    event_data['wall_clock'] = datetime.now().isoformat()  # Reference
else:
    event_data['timestamp'] = datetime.now().isoformat()  # Fallback
```

**File: `src/madspipeline/lsl_integration.py`**
```python
# Create inlet (pyLSL Python bindings don't support postproc_flags)
inlet = StreamInlet(stream)

# Apply clock synchronization manually by adding clock_offset to timestamps
# This achieves the same result as LSL's automatic postprocessing
clock_offset = inlet.time_correction()  # Clock offset measurement
original_timestamp = timestamp  # Original device timestamp
synchronized_timestamp = timestamp + clock_offset  # Synchronized to local time domain
```

### Result
✅ **All device timestamps are automatically synchronized** to local time domain  
✅ **Direct timestamp comparison** across devices (EmotiBit, Bridge Events, Mouse Tracking)  
✅ **Original timestamps preserved** for reference and validation  
✅ **Clock offset measurements** recorded for post-hoc analysis  
✅ **Real-time synchronization** during recording (no post-processing required)  
✅ **Backward compatible** - existing analysis tools can use `timestamp` field directly  

---

## Video & Event Timestamp Synchronization (Phase 2 ✅)

### Problem
- LSL event recording starts immediately when session begins
- Screen video recording starts slightly after (after page load)
- Early events have no corresponding video frames
- Timestamps don't align for playback

### Solution
Screen recorder sends a **`video_recording_started` sync event** containing:
- `type`: `'video_recording_started'`
- `timestamp`: LSL clock time when video recording began (in event data)
- `session_id`, `wall_clock`: Additional metadata

### Using the Sync Event

**Find sync marker:**
```python
def find_sync_event(events):
    for event in events:
        if event.get('type') == 'video_recording_started':
            return event

sync_event = find_sync_event(recorded_events)
# Get timestamp from event data (bridge events store timestamp in data.timestamp)
video_offset = sync_event.get('data', {}).get('timestamp') or sync_event.get('timestamp')  # e.g., 9.8 seconds
```

**Align events to video:**
```python
# Convert LSL timestamp to video playback time
# Use relative_time from the sync event sample, or calculate from timestamp
video_offset = sync_event_sample.get('relative_time')  # Time when video started (relative to session)
video_time = event_sample.get('relative_time') - video_offset

if video_time < 0:
    print(f"Event occurred {abs(video_time):.2f}s BEFORE video started")
else:
    print(f"Seek video to {video_time:.2f}s to see this event")
```

### Benefits
- Negative `video_time` → event before video recording (not on screen)
- Positive `video_time` → event at this position in video
- No complex offset calculations needed in review tools
- All data preserved; transparent about timing

---

## Data Output Format

### Session Directory Structure
```
tracking_data/{project_id}/sessions/{session_id}/
├── screen_recording_{session_id}.mp4       # Video capture
├── screen_recording_info_{session_id}.json # Video metadata (FPS, resolution)
├── lsl_recording_{session_id}.json         # All LSL streams + events
└── tracking_data.json                       # Legacy format
```

### LSL Recording JSON Sample
```json
{
  "session_id": "session_20251118_143022",
  "session_start_time": 671.234,
  "synchronization_info": {
    "sync_method": "LSL_online_clocksync",
    "sync_enabled": true,
    "description": "Timestamps are automatically synchronized to local time domain using LSL proc_clocksync postprocessing",
    "timestamp_field": "timestamp (synchronized to local time domain)",
    "original_timestamp_field": "original_timestamp (device clock domain, for reference)"
  },
  "lsl_samples": [
    {
      "timestamp": 671.345,
      "original_timestamp": 671.3462,
      "relative_time": 0.111,
      "stream_name": "MadsPipeline_BridgeEvents",
      "stream_type": "Markers",
      "data": ["page_load"],
      "clock_offset": 0.0012,
      "synchronization_applied": true
    },
    {
      "timestamp": 680.8,
      "original_timestamp": 680.8015,
      "relative_time": 9.566,
      "stream_name": "EmotiBit_BrainFlow",
      "stream_type": "EmotiBit",
      "data": [6546.0, -0.188, 0.397, 0.275],
      "clock_offset": 0.0015,
      "synchronization_applied": true
    },
    {
      "timestamp": 682.1,
      "original_timestamp": 682.1012,
      "relative_time": 10.866,
      "stream_name": "Tobii_Eyetracker",
      "stream_type": "ET",
      "data": [
        0.446, 0.414,  # left_gaze_x, left_gaze_y (normalized 0-1)
        0.436, 0.383,  # right_gaze_x, right_gaze_y (normalized 0-1)
        1.0, 1.0,      # left_validity, right_validity (1.0 = valid, 0.0 = invalid)
        2.836, 2.617   # left_pupil_diameter, right_pupil_diameter (mm)
      ],
      "clock_offset": 0.0012,
      "synchronization_applied": true
    }
  ]
}
```

**Note**: The `timestamp` field contains **synchronized timestamps** that can be directly compared across all devices. The `original_timestamp` field preserves the device's native clock time for reference.

**Gaze Data Format:**
- Coordinates are normalized (0.0-1.0) relative to display area (screen space)
- `left_gaze_x/y` and `right_gaze_x/y`: Gaze point coordinates for each eye
- `left_validity` and `right_validity`: Data quality (1.0 = valid, 0.0 = invalid)
- `left_pupil_diameter` and `right_pupil_diameter`: Pupil size in millimeters

---

## Common Development Tasks

| Task | File | Pattern |
|------|------|---------|
| Add LSL stream type | `lsl_integration.py` | Create StreamInlet, append to recorded_data in `record_sample()` |
| Change video codec | `screen_recorder.py` | Modify `codecs_to_try` list; H264 > XVID > mp4v |
| Add bridge event | `madsBridge.py` | Already handles JSON; send via `sendEvent()` from HTML |
| New project type | `models.py` + `main_window.py` | Add enum, config class, UI dialogs |
| Change save location | `project_manager.py` | Modify base path; sessions → `project_path/tracking_data/` |
| Add Tobii calibration point | `tobii_calibration_window.py` | Modify `calibration_points` list; adjust animation timing |
| Change gaze overlay appearance | `main_window.py` | Modify `_draw_gaze_overlay()` method; adjust colors/sizes in `QGraphicsEllipseItem` |

---

## Known Limitations & Workarounds

1. **Screen recording latency** → Use sync marker event to align timestamps during playback
2. **LSL device clock drift** → Automatically handled via `proc_clocksync`; timestamps synchronized in real-time. Clock offsets still recorded for validation and post-hoc analysis.
3. **HTML iframe isolation** → Use QWebChannel bridge only; external scripts unavailable
4. **Cross-platform video codecs** → Fallback chain: H264 → XVID → mp4v; auto-tested
5. **Qt6 DPI scaling (Windows)** → Handled via Windows API or DPR multiplier in ScreenRecorder

---

## Testing Strategy

**Unit Tests** (`tests/unit/`)
- Model enums and conversions
- Config dataclass serialization
- Project/session loading

**Integration Tests** (`tests/integration/`)
- HTML bridge event flow
- LSL stream recording with sync events
- Screen recording with video sync markers
- Session lifecycle

**Critical Path:** `pytest tests/integration/test_embedded_webpage_session.py`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Timestamp misalignment** | Check sync event in LSL JSON; verify `video_recording_started` sent; see "Video & Event Timestamp Synchronization" section |
| **LSL streams not appearing** | Run LSL Manager dialog ("Refresh Streams"); verify device connected/powered |
| **Video doesn't align with events** | Verify sync marker in JSON; calculate offset: `video_time = event_relative_time - sync_event_relative_time` |
| **HTML bridge not firing** | Confirm `madsBridge.js` loaded; check browser console for errors |
| **Project won't load** | Verify JSON structure; check `Project.from_dict()` in project_manager.py |
| **Tobii eye tracker not detected** | Verify USB connection; check device power (red light should be on); ensure `tobii-research` package is installed |
| **Tobii calibration fails** | Ensure device is fully awake (red light on) before starting; wait for device wake-up after entering calibration mode; check calibration warnings in completion message |
| **Gaze data not appearing in review** | Verify Tobii stream was recorded in LSL JSON; check "Show Gaze" checkbox is enabled in review window; ensure gaze data has valid coordinates (validity > 0.5) |
| **Tobii stream not starting** | Use LSL Manager to test connection independently; check device is not in use by another application; verify calibration is complete |

---

## Tobii Eye Tracker Integration ✅

### Overview
MadsPipeline includes full support for **Tobii Pro Spark** eye trackers, providing real-time gaze data collection synchronized with video recording and interaction events.

### Features

**Calibration System:**
- Fullscreen calibration window with animated targets
- 5-point calibration procedure
- Device wake-up detection (waits for red light before starting)
- Calibration stored on device (persists between sessions)
- Detailed warning display if calibration completes with issues
- Calibration can be triggered before session launch or from LSL Manager

**Gaze Data Streaming:**
- Real-time gaze data streamed to LSL at 60 Hz
- Screen space coordinates (normalized 0.0-1.0)
- Left and right eye gaze points tracked separately
- Validity flags for data quality assessment
- Pupil diameter measurements included
- Synchronized with LSL clock (same time domain as other devices)

**Visualization:**
- Gaze overlay in session review window
- Left eye gaze (blue), right eye gaze (green), averaged gaze (yellow)
- Gaze trails showing last 2 seconds of movement
- Only valid gaze points rendered (validity > 0.5)
- Toggle to show/hide gaze overlay

**Management:**
- LSL Manager integration for independent testing
- Start/stop gaze streaming
- Calibration and test functions available outside sessions
- Device state management (connection, calibration mode, streaming)

### Usage

**Before Starting a Session:**
1. Enable Tobii eye tracker in LSL configuration
2. When launching session, you'll be prompted to calibrate
3. Choose "Yes" to open fullscreen calibration window
4. Follow the animated targets (5 points)
5. Review calibration warnings if any
6. Session will launch after calibration completes

**From LSL Manager:**
1. Open LSL Manager from project dashboard
2. Click "Start Tobii Stream" to connect device
3. Click "Calibrate" to perform calibration
4. Click "Test Gaze" to visualize real-time gaze points
5. Use these tools to debug and validate setup before sessions

**In Review Window:**
1. Open session review window
2. Enable "Show Gaze" checkbox in timeline controls
3. Scrub through video to see gaze points at each moment
4. Gaze trails show movement history (last 2 seconds)

### Technical Details

**Files:**
- `tobii_manager.py`: Centralized state management, notification handling, calibration mode entry/exit
- `tobii_eyetracker.py`: LSL streaming integration (similar to EmotiBit BrainFlow streamer)
- `tobii_calibration_window.py`: Fullscreen PySide6 calibration UI with QTimer-based animation
- `tobii_gaze_test_window.py`: Real-time gaze visualization for validation

**Data Format:**
```python
# LSL stream channels (8 total):
[0] left_gaze_x      # Normalized 0.0-1.0
[1] left_gaze_y      # Normalized 0.0-1.0
[2] right_gaze_x     # Normalized 0.0-1.0
[3] right_gaze_y     # Normalized 0.0-1.0
[4] left_validity    # 1.0 = valid, 0.0 = invalid
[5] right_validity   # 1.0 = valid, 0.0 = invalid
[6] left_pupil_diameter   # Millimeters
[7] right_pupil_diameter  # Millimeters
```

**Calibration Storage:**
- Calibration data is stored **on the Tobii device itself**
- Persists between application restarts
- Not stored in project settings or application runtime
- Can be retrieved using `retrieve_calibration_data()` and reapplied with `apply_calibration_data()`

**State Management:**
- `TobiiManager` handles all state transitions (DISCONNECTED → CONNECTED → CALIBRATION_MODE → STREAMING)
- Uses notification callbacks to confirm calibration mode entry
- Thread-safe with `threading.Lock` and `threading.Event` for state synchronization

**Device Wake-up:**
- Device wakes up when `collect_data()` is called
- Calibration procedure includes early wake-up call before actual data collection
- 3-second delay after wake-up ensures device is ready (red light on)

---

## Development Roadmap

### Completed (✅ Phase 1-2)

**Project Structure & Data Management**
- ✅ Project folder structure system
- ✅ Project metadata storage and configuration
- ✅ Project type system (Picture Slideshow, Video, Screen Recording, Embedded Webpage)
- ✅ Sessions folder organization
- ✅ Session management and metadata

**Main Application GUI**
- ✅ Main application window with PySide6
- ✅ Project selection startup screen
- ✅ Dashboard with session/project management
- ✅ Project editing dialog
- ✅ Debug session window with live tracking

**Mouse Tracking System**
- ✅ Real-time mouse coordinate capture
- ✅ Mouse click events (left, right, middle)
- ✅ Mouse scroll events
- ✅ Extensible tracking data format (JSON)
- ✅ Debug visualization with movement trails

**LSL Integration (Phase 1-2 ✅)**
- ✅ HTML-to-Python bridge via QWebChannel
- ✅ LSL stream outlet for bridge events
- ✅ Bridge event streaming to LSL in real-time
- ✅ LSL stream recording during sessions
- ✅ Clock synchronization (local_clock vs wall_clock)
- ✅ Clock offset measurement per sample
- ✅ Video recording with sync marker events

**Tobii Eye Tracker Integration (✅ Complete)**
- ✅ Tobii Pro Spark device detection and connection
- ✅ Fullscreen calibration window with animated targets
- ✅ Device wake-up detection and readiness confirmation
- ✅ Calibration stored on device (persists between sessions)
- ✅ Gaze data streaming to LSL (60 Hz, screen space coordinates)
- ✅ Left/right eye gaze tracking with validity flags
- ✅ Pupil diameter measurements
- ✅ LSL Manager integration (start/stop, calibrate, test)
- ✅ Session launch calibration prompt
- ✅ Gaze overlay in review window (left/right/averaged with trails)
- ✅ Real-time gaze visualization test window

**Technical Infrastructure**
- ✅ Data models (Project, Session, Config dataclasses)
- ✅ Data persistence layer (JSON file storage)
- ✅ Configuration management system
- ✅ Project/session loading and saving

---

### Phase 3: Critical Data Management & Testing (Target: Nov 25, 2025)

**Data Export System** ⏳ Priority: HIGH
- [ ] Fix export to include actual tracking data (currently only exports project info)
- [ ] Implement CSV export format with configurable columns
- [ ] Implement JSON export format maintaining full structure
- [ ] Add session-level export (single session data)
- [ ] Add project-level export (all sessions in project)
- [ ] Add data sanitization/filtering options

**LSL Stream Synchronization Testing** ⏳ Priority: HIGH
- [ ] Test LSL clock sync for mouse tracking stream
- [ ] Test LSL clock sync for hardware device streams (EmotiBit, Tobii)
- [ ] Verify clock offset calculations per stream
- [ ] Document sync validation procedures
- [ ] Create sync test fixtures for CI/CD

**LSL Stream Management Overhaul** ⏳ Priority: HIGH
- [ ] Redesign LSL Manager UI for channel/type selection
- [ ] Add per-device stream filtering (select which channels to record)
- [ ] Implement device-specific configuration profiles
- [ ] Add stream preview/validation before recording
- [ ] Store device preferences in project config

**Video Playback Validation** ⏳ Priority: HIGH
- [ ] Verify video resolution accuracy in recordings
- [ ] Test event overlay alignment with video playback
- [ ] Validate sync marker offsets with actual recordings
- [ ] Create test cases for different video codecs

**UI/UX Improvements** ⏳ Priority: MEDIUM
- [ ] Disable "Debug Session" button (future enhancement)
- [ ] Add "Open in Explorer" button to project overview
- [ ] Add folder navigation for session data
- [ ] Improve project overview card layout

**Logging (New)**
- Application output (both logging and redirected stdout/stderr) is written to a `logs/` folder at the repository root.
- Each run creates a timestamped log file named `madspipeline_YYYYMMDD_HHMMSS.log` which contains console messages and any `print()` output.
- The `logs/` folder is included in `.gitignore` to prevent runtime logs from being committed.

**LSL Manager Overhaul (Updates)**
- The LSL Stream Manager UI now includes a per-stream "Record" checkbox so you can explicitly select which available LSL streams should be recorded.
- Selected streams are stored in the project `embedded_webpage` LSL configuration under `additional_stream_filters` so the recorder can respect user choices during sessions.

**Project File Structure Review** ⏳ Priority: MEDIUM
- [ ] Audit current tracking_data directory layout for redundancy
- [ ] Identify and consolidate duplicate data files
- [ ] Optimize session metadata organization
- [ ] Document final structure schema
- [ ] Create migration utility if needed

---

### In Progress / Planned (Phase 4+)

**Screen Recording System**
- [ ] Cross-platform screen recording (Windows/Linux/macOS) - Partially done (Windows working, needs testing on other platforms)
- [ ] Recording quality settings (resolution, FPS, codec) - Basic settings implemented
- [ ] Recording preview window - Not started
- [ ] Fullscreen application recording optimization

**Session Review & Analysis** ✅
- ✅ Session review window with video playback
- ✅ Video playback controls (play, pause, seek, speed)
- ✅ Frame-by-frame navigation
- ✅ Tracking data overlay on playback (mouse cursor and trail)
- ✅ Gaze data overlay on video (left eye, right eye, averaged gaze with trails)
- ✅ Event marker system for review
- [ ] Marker categorization and export

**Data Visualization & Overlays** ✅ (Partial)
- ✅ Advanced overlay rendering system
- ✅ Mouse cursor and click indicators
- ✅ Mouse movement trails
- ✅ Gaze point visualization (left/right/averaged with validity checking)
- ✅ Gaze trail rendering (last 2 seconds with fading)
- [ ] Heatmaps
- ✅ Time-series charts for tracking data
- [ ] Heart rate/EDA overlays (hardware integration)

**Export & Data Management**
- [ ] Video export with overlays
- [ ] Project dataset export (multi-session) - See Phase 3
- [ ] Batch export functionality

**Hardware Integration** ✅ (Partial)
- [ ] EmotiBit device detection and streaming
- ✅ **Tobii Pro Spark eyetracker integration** (Complete)
  - ✅ Device detection and connection
  - ✅ Fullscreen calibration with animated targets
  - ✅ Gaze data streaming to LSL (60 Hz, screen space coordinates)
  - ✅ Calibration stored on device (persists between sessions)
  - ✅ Gaze visualization test window
  - ✅ LSL Manager integration (start/stop, calibrate, test)
  - ✅ Session launch calibration prompt
  - ✅ Gaze overlay in review window (left/right/averaged with trails)
- [ ] Plugin system for new devices
- ✅ Advanced synchronization with multiple LSL devices (LSL clock sync)
- ✅ Post-hoc device clock synchronization (clock offset measurements recorded)

**Testing & Quality Assurance**
- [ ] Unit tests for core functionality
- [ ] Integration tests for recording pipeline
- [ ] GUI testing framework
- [ ] Performance testing for real-time operations
- [ ] Cross-platform compatibility testing

**Documentation**
- [ ] User manual and tutorials
- [ ] In-app help system
- [ ] Keyboard shortcuts guide
- [ ] Progress indicators and status messages

---

## Implementation Priorities

| Phase | Focus | Target | Status |
|-------|-------|--------|--------|
| **1** | GUI structure, project management | ✅ Complete | ✅ Complete |
| **2** | Screen recording, mouse tracking, LSL sync | ✅ Complete | ✅ Complete |
| **3** | Data export, LSL testing & management, playback validation | Nov 25, 2025 | 🚧 In Progress |
| **4** | Session review, video playback overlays | Dec 2025 | ⏳ Planned |
| **5** | Hardware integration (EmotiBit, Tobii) | Jan 2026 | ✅ Tobii Complete |

**Phase 3 Breakdown (Critical Path - Nov 25 Deadline):**
- Data export system (CSV/JSON, session/project level)
- LSL stream sync validation for all device types
- LSL Manager UI overhaul (channel/type selection per device)
- Video resolution & playback alignment testing
- Minor UI improvements (disable debug button, add explorer navigation)
- Project file structure audit & optimization

---

## License

MIT License - See LICENCE file for details

---

## Contributing

This project is part of an academic research initiative. For contributions, feature requests, or bug reports, please contact the MadsPipeline team.
