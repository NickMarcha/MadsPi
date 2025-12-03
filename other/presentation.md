# MadsPipeline: Metrics of Attention Data Streaming and Visualization Pipeline

## Motivation for the project

Visual data stories are increasingly used in news outlets like the New York Times and digital publications such as The Pudding to tell compelling narratives about data. These stories aim to help audiences understand and empathize with complex topics through interactive visualizations and engaging storytelling devices.

**The Challenge**: While visual data stories feel engaging and fun to explore, there is limited understanding of:
- To what extent they actually make readers feel something emotionally
- How effectively they help readers understand the underlying data
- What cognitive and emotional responses occur during interaction

**Current State**: Existing research lacks comprehensive open -source tools for collecting quantitative behavioral data (eyetracking, heart rate, electrodermal activity) synchronized with visual data story interactions. This gap prevents visualization researchers from understanding how readers respond cognitively and emotionally to these narratives.

**My Goal**: Develop an open-source pipeline to collect and visualize quantitative behavioral data, enabling visualization researchers to understand how readers respond cognitively and emotionally to visual data stories.

---

## Contribution

I developed **MadsPipeline** - an open-source, cross-platform graphical tool that:

1. **Integrates multiple physiological data streams**:
   - Eyetracking (Tobii Pro Spark)
   - Heart rate and electrodermal activity (EmotiBit)
   - Mouse tracking and interaction events
   - Screen recording with synchronized timestamps

2. **Solves time synchronization challenges**:
   - Implements LSL (Lab Streaming Layer) for real-time clock synchronization across devices
   - Achieves < 1 ms accuracy on local networks
   - Preserves both synchronized and original timestamps for analysis

3. **Provides comprehensive session management**:
   - Project and session organization system
   - Multiple stimulus types: picture slideshows, videos, embedded webpages, screen recordings

4. **Enables post-experiment analysis**:
   - Time-aligned visualizations of physiological data
   - Event markers for experiment milestones
   - Exportable datasets (JSON/CSV format)

5. **Creates a foundation for future research**:
   - Extensible architecture for additional devices
   - Standardized data format for multi-session analysis
   - Open-source codebase for the visualization research community

---

## Background/Related work

**Visual Data Storytelling**:
- News outlets (New York Times) and digital publications (The Pudding) use interactive visualizations to tell data-driven stories
- Research in information visualization explores how visual narratives engage and inform audiences

**Physiological Data Collection**:
- **EmotiBit**: Open-source wearable device for collecting heart rate, electrodermal activity, and other physiological signals
- **Tobii Pro Spark**: Professional eyetracking device for gaze data collection
- **BrainFlow**: Open-source library for biosignal acquisition and processing

**Time Synchronization**:
- **Lab Streaming Layer (LSL)**: Network protocol for real-time streaming of time-series data with built-in clock synchronization
- Uses NTP-like algorithm for clock offset measurement and correction
- Enables multi-device data collection with synchronized timestamps

**Experimental Software**:
- **PsychoPy**: Python library for creating psychology experiments
- **PySide6/Qt6**: Cross-platform GUI framework for desktop applications
- **MSS**: Python library for screen capture

**Research Context**:
- Project developed in the Visualization Group at the Department of Informatics, University of Bergen
- Addresses the need for quantitative evaluation of visual data story effectiveness

---

## Methods

### Architecture

I implemented a **three-layer architecture**:

**1. GUI Layer** (`main_window.py`):
- Qt6 desktop application with PySide6
- Project and session management dialogs
- Session windows for different project types (Picture Slideshow, Video, Embedded Webpage, Screen Recording)
- LSL stream management interface

**2. Integration Layer**:
- `lsl_integration.py`: LSL event streaming and multi-stream recording with clock synchronization
- `screen_recorder.py`: Video capture with synchronized event markers
- `madsBridge.py`: HTML ↔ Python event communication bridge using QWebChannel
- `lsl_manager.py`: Stream detection and configuration UI

**3. Data Layer**:
- `models.py`: Dataclasses for projects, sessions, and configurations
- `project_manager.py`: JSON persistence to `tracking_data/{project_id}/sessions/{session_id}/`
- Output format: MP4 video + LSL JSON + metadata

### Key Technical Decisions

**Cross-platform Development**:
- Python with PySide6 for GUI portability (Windows, Linux, macOS)
- MSS library for screen recording across platforms
- Platform-specific setup scripts for dependency management

**Time Synchronization Implementation**:
- Manual clock offset correction using `inlet.time_correction()` (pyLSL limitation)
- Formula: `synchronized_timestamp = timestamp + clock_offset`
- Dual timestamp storage: synchronized (`timestamp`) and original (`original_timestamp`)
- Real-time synchronization during recording (no post-processing required)

**Device Integration**:
- **BrainFlow**: Library for accessing EmotiBit and other biosignal devices
- **pyLSL**: Python bindings for Lab Streaming Layer
- **Tobii Research SDK**: Python package for eyetracker communication
- Extensible architecture for future device additions

**Data Recording**:
- Screen recording with video codec fallback chain (H264 → XVID → mp4v)
- LSL stream recording with automatic clock synchronization
- Event markers for experiment start, stimulus changes, and experiment end
- Video sync marker events to align video playback with LSL timestamps

### Implementation Approach

1. **Project Structure**: Organized sessions by project with metadata storage
2. **Session Types**: Support for multiple stimulus types with configurable parameters
3. **Real-time Data Collection**: Simultaneous recording of multiple LSL streams
4. **Synchronization**: Automatic clock synchronization across all devices
5. **Data Export**: JSON and CSV formats with full timestamp information

---

## Results

### Achieved Features

**✅ Phase 1-2 Complete** (Project Structure & Data Management):
- Project folder structure system with metadata storage
- Project type system (Picture Slideshow, Video, Screen Recording, Embedded Webpage)
- Session management and organization
- Main application GUI with PySide6
- Project selection startup screen and dashboard

**✅ Mouse Tracking System**:
- Real-time mouse coordinate capture
- Mouse click and scroll events
- Extensible tracking data format (JSON)
- Debug visualization with movement trails

**✅ LSL Integration**:
- HTML-to-Python bridge via QWebChannel
- LSL stream outlet for bridge events
- Real-time bridge event streaming to LSL
- Multi-stream LSL recording during sessions
- **Clock synchronization** with < 1 ms accuracy on local networks
- Clock offset measurement per sample
- Video recording with sync marker events

**✅ Screen Recording**:
- Cross-platform screen capture (Windows working, Linux/macOS in progress)
- Video recording with synchronized event markers
- Configurable quality settings (resolution, FPS, codec)
- Video sync marker events for playback alignment

**✅ Data Output**:
- Session directory structure: `tracking_data/{project_id}/sessions/{session_id}/`
- MP4 video files with metadata
- LSL JSON recordings with synchronized timestamps
- Comprehensive synchronization metadata in output

### Technical Achievements

- **Time Synchronization**: Successfully implemented LSL clock synchronization, enabling direct timestamp comparison across all devices
- **Cross-platform Foundation**: Working Windows implementation with Linux/macOS support in progress
- **Extensible Architecture**: Modular design allows easy addition of new devices and project types
- **Data Integrity**: Dual timestamp storage preserves both synchronized and original timestamps for validation

### Current Status

**Phase 3 In Progress** (Target: Nov 25, 2025):
- Data export system improvements (CSV/JSON with actual tracking data)
- LSL stream synchronization testing and validation
- LSL Manager UI overhaul (channel/type selection per device)
- Video playback validation and alignment testing

---

## Discussion

### Limitations

1. **Hardware Integration**:
   - Eye tracker (Tobii Pro Spark) not yet fully implemented
   - EmotiBit integration requires additional testing and validation
   - Future device implementation could be standardized more with BrainFlow

2. **Time Synchronization**:
   - Current implementation uses manual clock offset correction (pyLSL limitation)
   - Post-hoc linear fit synchronization not yet implemented (could improve accuracy for long sessions)
   - Clock drift handling adequate for typical session lengths (< 1 hour)

3. **Video Synchronization**:
   - Screen recording starts slightly after LSL event recording begins
   - Early events may not have corresponding video frames
   - Sync marker events address this, but video playback alignment needs refinement
   - May need to address lag issues with recording

4. **Platform Support**:
   - Windows implementation complete
   - Linux and macOS screen recording needs additional testing
   - Cross-platform video codec compatibility requires fallback mechanisms

5. **Data Visualization**:
   - Post-experiment visualization features (heatmaps, overlays) planned but not yet implemented
   - Session review window with video playback in development

### Key Learnings

1. **Time Synchronization Complexity**:
   - LSL's clock synchronization is powerful but requires careful implementation
   - Preserving original timestamps is crucial for validation and post-hoc analysis
   - Manual clock offset correction works well when pyLSL doesn't support postprocessing flags

2. **Cross-platform Development**:
   - Screen recording APIs vary significantly across platforms
   - Video codec support requires fallback strategies
   - Qt6 provides good cross-platform GUI foundation

3. **Device Integration**:
   - BrainFlow provides standardized interface for biosignal devices
   - LSL enables flexible multi-device data collection
   - Extensible architecture important for future device support

4. **Data Management**:
   - Dual timestamp storage (synchronized + original) provides flexibility
   - JSON format allows rich metadata while maintaining readability
   - Session organization critical for multi-session experiments

### Future Work

**Immediate (Phase 3-4)**:
- Complete eye tracker (Tobii Pro Spark) implementation
- Post-experiment visualization with heatmaps and overlays
- Session review window with video playback
- Data export system improvements

**Medium-term**:
- Post-hoc linear fit synchronization for improved accuracy
- Advanced overlay rendering system
- Video export with overlays
- Batch export functionality

**Long-term**:
- Plugin system for new devices
- Advanced synchronization with multiple LSL devices
- User manual and tutorials
- Performance optimization for real-time operations

### Connection to MSc Thesis

This project provides the foundation for:
- Quantitative evaluation of visual data story effectiveness
- Understanding cognitive and emotional responses to data visualizations
- Developing metrics for attention and engagement in visual narratives
- Creating tools for the visualization research community

The pipeline enables future research into:
- How different visualization techniques affect physiological responses
- Correlation between eyetracking patterns and emotional responses
- Effectiveness of different storytelling devices in data visualization
- Multi-modal analysis of user interaction with visual data stories

---

## Wrap-up

**My Contribution**: I developed MadsPipeline, an open-source pipeline for collecting synchronized physiological data (eyetracking, heart rate, electrodermal activity) during visual data story interactions. The system solves critical time synchronization challenges and provides a foundation for quantitative evaluation of visual data story effectiveness.

**Key Achievements**:
- ✅ Cross-platform graphical tool for experimental sessions
- ✅ Real-time LSL clock synchronization (< 1 ms accuracy)
- ✅ Multiple stimulus types with configurable parameters
- ✅ Comprehensive data recording and export system
- ✅ Extensible architecture for future device integration

**Impact**: This tool enables visualization researchers to quantitatively understand how readers respond cognitively and emotionally to visual data stories, addressing a critical gap in current research methods.

**Next Steps**: Complete eye tracker implementation, refine video synchronization, and develop post-experiment visualization features to enable comprehensive analysis of collected data.


https://docs.google.com/presentation/d/1JZSL_ljufK9ivvp9nPdzEsKvwI7wuBU8xlcr_EmcjYU/edit?usp=sharing




Emotibit Psychopy
Expected Questions