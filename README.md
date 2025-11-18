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
│   └── lsl_manager.py             # LSL stream management UI
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
Previously, bridge events and LSL streams were in **different time domains**:
- Bridge events: Python datetime (wall clock) ❌
- LSL samples: LSL `local_clock()` (steady, boot-relative) ❌

### Solution Implemented
1. **Bridge events now use `local_clock()`** for LSL time domain alignment
2. **LSL samples record clock offsets** via `inlet.time_correction()` per sample
3. **Session JSON preserves synchronization metadata** for post-hoc analysis

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
# Each LSL sample now includes clock offset
clock_offset = inlet.time_correction()  # Remote clock offset in seconds
recorded_sample['clock_offset'] = clock_offset
recorded_sample['local_time_when_recorded'] = local_clock()
```

### Result
✅ Bridge events align chronologically with LSL streams  
✅ Multi-device synchronization infrastructure in place  
✅ Zero breaking changes; backward compatible  
✅ Clock offsets enable post-hoc device synchronization  

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
- `lsl_timestamp`: LSL clock time when video recording began
- `session_id`, `wall_clock`: Additional metadata

### Using the Sync Event

**Find sync marker:**
```python
def find_sync_event(events):
    for event in events:
        if event.get('type') == 'video_recording_started':
            return event

sync_event = find_sync_event(recorded_events)
video_offset = sync_event['lsl_timestamp']  # e.g., 9.8 seconds
```

**Align events to video:**
```python
# Convert LSL timestamp to video playback time
video_time = event['lsl_timestamp'] - video_offset

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
    "sync_method": "LSL_CLOCK",
    "bridge_events_time_domain": "lsl_local_clock"
  },
  "lsl_samples": [
    {
      "timestamp": 671.345,
      "stream_name": "MadsPipeline_BridgeEvents",
      "stream_type": "Markers",
      "data": ["page_load"],
      "clock_offset": 0.0012
    },
    {
      "timestamp": 680.8,
      "stream_name": "video_recording_started",
      "stream_type": "Markers",
      "data": ["sync_marker"],
      "lsl_timestamp": 9.8
    }
  ]
}
```

---

## Common Development Tasks

| Task | File | Pattern |
|------|------|---------|
| Add LSL stream type | `lsl_integration.py` | Create StreamInlet, append to recorded_data in `record_sample()` |
| Change video codec | `screen_recorder.py` | Modify `codecs_to_try` list; H264 > XVID > mp4v |
| Add bridge event | `madsBridge.py` | Already handles JSON; send via `sendEvent()` from HTML |
| New project type | `models.py` + `main_window.py` | Add enum, config class, UI dialogs |
| Change save location | `project_manager.py` | Modify base path; sessions → `project_path/tracking_data/` |

---

## Known Limitations & Workarounds

1. **Screen recording latency** → Use sync marker event to align timestamps during playback
2. **LSL device clock drift** → Recorded in `clock_offset` per sample; post-hoc correction available
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
| **Video doesn't align with events** | Verify sync marker in JSON; calculate offset: `video_time = event_timestamp - sync_event['lsl_timestamp']` |
| **HTML bridge not firing** | Confirm `madsBridge.js` loaded; check browser console for errors |
| **Project won't load** | Verify JSON structure; check `Project.from_dict()` in project_manager.py |

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

**Technical Infrastructure**
- ✅ Data models (Project, Session, Config dataclasses)
- ✅ Data persistence layer (JSON file storage)
- ✅ Configuration management system
- ✅ Project/session loading and saving

---

### In Progress / Planned

**Screen Recording System**
- [ ] Cross-platform screen recording (Windows/Linux/macOS) - Partially done (Windows working, needs testing on other platforms)
- [ ] Recording quality settings (resolution, FPS, codec) - Basic settings implemented
- [ ] Recording preview window - Not started
- [ ] Fullscreen application recording optimization

**Session Review & Analysis**
- [ ] Session review window with video playback
- [ ] Video playback controls (play, pause, seek, speed)
- [ ] Frame-by-frame navigation
- [ ] Tracking data overlay on playback
- [ ] Event marker system for review
- [ ] Marker categorization and export

**Data Visualization & Overlays**
- [ ] Advanced overlay rendering system
- [ ] Mouse cursor and click indicators
- [ ] Movement trails and heatmaps
- [ ] Time-series charts for tracking data
- [ ] Heart rate/EDA overlays (hardware integration)

**Export & Data Management**
- [ ] Session data export (JSON, CSV)
- [ ] Video export with overlays
- [ ] Project dataset export (multi-session)
- [ ] Batch export functionality

**Future Hardware Integration**
- [ ] EmotiBit device detection and streaming
- [ ] Tobii Pro Spark eyetracker integration
- [ ] Plugin system for new devices
- [ ] Advanced synchronization with multiple LSL devices
- [ ] Post-hoc device clock synchronization

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

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | GUI structure, project management | ✅ Complete |
| **2** | Screen recording, mouse tracking, LSL sync | ✅ Complete |
| **3** | Session review, video playback, overlays | 🚧 In Progress |
| **4** | Advanced visualization, export features | ⏳ Planned |
| **5** | Hardware integration (EmotiBit, Tobii) | ⏳ Planned |

---

## License

MIT License - See LICENCE file for details

---

## Contributing

This project is part of an academic research initiative. For contributions, feature requests, or bug reports, please contact the MadsPipeline team.
