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
│   ├── tobii_gaze_test_window.py  # Gaze visualization test window
│   └── emotibit_brainflow.py      # EmotiBit integration
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (models, data)
│   └── integration/               # Integration tests (GUI, LSL, bridge)
├── .github/
│   └── copilot-instructions.md    # AI agent coding guidelines
├── scripts/                       # Setup scripts (Windows/Linux/macOS)
├── docs/                          # Project documentation
│   ├── MadsBridge.MD              # HTML bridge usage
│   └── ...
├── pyproject.toml                 # Project configuration
├── pytest.ini                     # Test configuration
└── requirements-dev.txt          # Development dependencies
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
- `tobii_manager.py`: Tobii eye tracker state management, calibration mode, and notifications
- `tobii_eyetracker.py`: Tobii gaze data streaming to LSL (screen space coordinates)
- `tobii_calibration_window.py`: Fullscreen calibration interface with animated targets
- `tobii_gaze_test_window.py`: Real-time gaze visualization for calibration validation
- `emotibit_brainflow.py`: EmotiBit BrainFlow integration

**Data Layer**

- `models.py`: Dataclasses for projects, sessions, configurations
- `project_manager.py`: JSON persistence to `tracking_data/{project_id}/sessions/{session_id}/`
- Output: MP4 video + LSL JSON + metadata

### Project Types

| Type                  | Config                   | Features                                              |
| --------------------- | ------------------------ | ----------------------------------------------------- |
| **Picture Slideshow** | `PictureSlideshowConfig` | Auto-advance, slide duration, fade/slide transitions  |
| **Video**             | `VideoConfig`            | Auto-play, seek to start/end times, looping            |
| **Embedded Webpage**  | `EmbeddedWebpageConfig`  | HTML bridge, LSL events, screen recording, fullscreen  |
| **Screen Recording**  | `ScreenRecordingConfig`  | Window/fullscreen capture, FPS, resolution, codecs    |

---

## Development

### Running Tests

```bash
python -m pytest tests -v
python -m pytest tests/unit -v
python -m pytest tests/integration -v
python -m pytest tests --cov=src/madspipeline --cov-report=html
```

### Code Quality

```bash
black --line-length=88 src/
flake8 src/
isort src/
mypy src/madspipeline/
```

Configured in `pyproject.toml`; VS Code auto-formats on save.

### Debug Configurations (VS Code / Cursor)

- Launch Main Application, Launch with run.py, Debug Current Test File, Run All / Unit / Integration Tests

---

## LSL Time Synchronization (Phase 1)

- **Problem:** Device timestamps were in different clock domains; not directly comparable.
- **Solution:** Manual clock correction (pyLSL has no `postproc_flags`): we apply `clock_offset` from `inlet.time_correction()` so `timestamp = original_timestamp + clock_offset`. Bridge events use `local_clock()` for the same time domain.
- **Storage:** `timestamp` (synchronized), `original_timestamp` (device clock), `clock_offset` and optional `linear_fit_offset` for post-hoc analysis.
- **Result:** All device timestamps are comparable; accuracy < 1 ms on local networks.

See **[CURRENT_TIME_IMPLEMENTATION.md](CURRENT_TIME_IMPLEMENTATION.md)** for field semantics and playback, and **[TIME_SYNCHRONIZATION.md](TIME_SYNCHRONIZATION.md)** for theory and post-hoc options.

---

## Video & Event Timestamp Synchronization (Phase 2)

- **Problem:** LSL recording starts at session start; video starts slightly later; early events have no frames.
- **Solution:** Screen recorder sends a `video_recording_started` event with top-level **`timestamp`** (LSL time when recording started). Recording info JSON also stores `lsl_first_frame_time` for alignment.
- **In code:** Sync event has `type: 'video_recording_started'` and **`timestamp`** (not `lsl_timestamp`). For playback, use `screen_recording_info.lsl_first_frame_time` and `session_start_time` from LSL JSON, or find the sync event and use `event['timestamp']` to compute video time.

See **CURRENT_TIME_IMPLEMENTATION.md** for playback time calculation and review window behavior.

---

## Data Output Format

### Session Directory Structure

```
tracking_data/{project_id}/sessions/{session_id}/
├── screen_recording_{session_id}.mp4
├── screen_recording_info_{session_id}.json   # FPS, resolution, lsl_first_frame_time
├── lsl_recording_{session_id}.json           # All LSL streams + events
└── tracking_data.json                        # Legacy format
```

### LSL Recording JSON (excerpt)

- **sync_method** in metadata: `"manual_clock_offset_correction"` (timestamps synchronized via clock_offset).
- Each sample: `timestamp` (synchronized), `original_timestamp`, `relative_time`, `clock_offset`, and optionally `linear_fit_offset`.
- Gaze: normalized 0–1, validity, pupil diameter (mm).

See **[single dataentry.md](single%20dataentry.md)** for full EmotiBit and Bridge event samples and channel mapping.

---

## Common Development Tasks

| Task                        | File                           | Pattern                                                        |
| --------------------------- | ------------------------------ | -------------------------------------------------------------- |
| Add LSL stream type         | `lsl_integration.py`           | Create StreamInlet, append in `record_sample()`                |
| Change video codec         | `screen_recorder.py`           | Modify `codecs_to_try`; H264 > XVID > mp4v                     |
| Add bridge event            | `madsBridge.py`                | Send via `sendEvent()` from HTML; bridge handles JSON         |
| New project type            | `models.py` + `main_window.py` | Add enum, config class, UI dialogs                             |
| Change save location        | `project_manager.py`           | Base path; sessions under `project_path/tracking_data/`       |
| Add Tobii calibration point | `tobii_calibration_window.py`  | Modify `calibration_points`; animation timing                  |
| Change gaze overlay         | `main_window.py`               | `_draw_gaze_overlay()`; colors/sizes in `QGraphicsEllipseItem`  |

---

## Known Limitations & Workarounds

1. **Screen recording latency** → Use sync marker / `lsl_first_frame_time` to align timestamps in playback.
2. **LSL device clock drift** → Handled via clock_offset (and optional linear_fit_offset); both recorded.
3. **HTML iframe isolation** → Use QWebChannel bridge only.
4. **Cross-platform video codecs** → Fallback: H264 → XVID → mp4v.
5. **Qt6 DPI scaling (Windows)** → Handled via Windows API or DPR in ScreenRecorder.

---

## Testing Strategy

- **Unit:** models, configs, project/session loading.
- **Integration:** HTML bridge, LSL recording with sync events, screen recording, session lifecycle.
- **Critical path:** `pytest tests/integration/test_embedded_webpage_session.py`

---

## Troubleshooting

| Issue                     | Solution                                                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Timestamp misalignment    | Check sync event (use top-level `timestamp`) or `screen_recording_info.lsl_first_frame_time`; see CURRENT_TIME_IMPLEMENTATION.md |
| LSL streams not appearing | LSL Manager → Refresh Streams; verify device connected/powered                                                                  |
| Video doesn't align with events | Use `video_time = relative_time - video_lsl_offset`; offset from recording info or sync event                                |
| HTML bridge not firing    | Confirm `madsBridge.js` loaded; check console                                                                                     |
| Project won't load        | Verify JSON and `Project.from_dict()` in project_manager.py                                                                      |
| Tobii not detected        | USB, power (red light), `tobii-research` installed                                                                                |
| Tobii calibration fails   | Device awake (red light); wait after entering calibration                                                                       |
| Gaze not in review        | Tobii stream in LSL JSON; "Show Gaze" enabled; validity > 0.5                                                                     |

---

## Tobii Eye Tracker Integration

- **Calibration:** Fullscreen, 5-point, stored on device; wake-up detection.
- **Gaze:** 60 Hz LSL, normalized 0–1, left/right + validity + pupil diameter.
- **Review:** Gaze overlay (left/right/averaged, trails); "Show Gaze" toggle.
- **Management:** LSL Manager: start/stop stream, calibrate, test gaze.

See README "Project Structure" and "Architecture" for file roles; **[docs/MadsBridge.MD](docs/MadsBridge.MD)** for HTML bridge usage.

---

## Development Roadmap

- **Phase 1–2:** GUI, project/session management, LSL sync, video sync, Tobii integration — complete.
- **Phase 3 (in progress):** Data export (CSV/JSON), LSL sync testing, LSL Manager overhaul, video playback validation, UI improvements, project file structure audit.
- **Phase 4+:** Session review enhancements, heatmaps, export with overlays, EmotiBit hardening, documentation.

---

## License

MIT License — see LICENCE file.

---

## Contributing

This project is part of an academic research initiative. For contributions, feature requests, or bug reports, please contact the NickMarcha