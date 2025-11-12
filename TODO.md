# GUI and Screen Recording Implementation Todo List

## 1. Project Structure & Data Management

- [x] Create project folder structure system
  - [x] Project selection/creation dialog
  - [x] Project metadata storage (description, creation date, etc.)
  - [x] Project type system (Picture Slideshow, Video, Screen Recording, Embedded Webpage)
  - [x] Type-specific configuration and metadata
  - [x] Sessions folder organization within each project
  - [x] Project configuration file format (JSON/YAML)
- [x] Implement session management
  - [x] Session naming and metadata
  - [x] Session data organization (screen recordings, tracking data, markers)
  - [x] Session export/import functionality

## 2. Main Application GUI

- [x] Create main application window with PySide6
- [x] Implement project selection startup screen
- [x] Design main dashboard with options:
  - [x] Start new session
  - [x] Debug session with real-time tracking
  - [x] Edit project settings
  - [x] Review existing sessions
  - [x] Export complete dataset
  - [x] Project settings
- [x] Add navigation between different sections
- [x] Implement project switching functionality
- [x] Project type selection in creation dialog
- [x] Project type display in dashboard and lists
- [x] Project editing after creation (single place for all configuration)
- [x] Debug session window with live tracking visualization

## 3. Screen Recording System

- [ ] Implement cross-platform screen recording
  - [ ] Windows: Use `pyautogui` + `opencv-python` or `mss`
  - [ ] Linux: Use `mss` or `ffmpeg-python`
  - [ ] macOS: Use `mss` or `avfoundation`
- [ ] Add recording controls (start, stop, pause)
- [ ] Implement recording quality settings (resolution, FPS, codec)
- [ ] Add recording preview window
- [ ] Handle fullscreen application recording

## 4. Mouse Tracking System

- [x] Implement mouse position tracking
  - [x] Real-time mouse coordinate capture
  - [x] Mouse click events (left, right, middle)
  - [x] Mouse scroll events
  - [ ] Mouse movement velocity tracking
- [x] Design extensible tracking data format
  - [x] JSON structure for future hardware integration
  - [x] Timestamp synchronization with screen recording
  - [x] Event-based data structure for markers
- [x] Debug session with live tracking visualization
- [x] Mouse movement trails and click indicators

## 5. Session Recording Interface

- [ ] Create recording session window
- [ ] Implement stimulus presentation system
  - [ ] Image/video/webpage display capabilities
  - [ ] Stimulus timing controls
  - [ ] Stimulus sequence management
- [ ] Add real-time tracking visualization
  - [ ] Mouse position overlay on screen
  - [ ] Live tracking data display
- [ ] Implement session controls and monitoring
- [ ] **CRITICAL: Integrate HTML-to-Python bridge with embedded webpage sessions**
  - [ ] Set up QWebChannel bridge in EmbeddedWebpageSessionWindow
  - [ ] Connect bridge to receive events from HTML pages
  - [ ] Parse and validate bridge messages/events
- [ ] **CRITICAL: Implement LSL streaming from bridge events**
  - [ ] Create LSL stream outlet for bridge events
  - [ ] Stream events from HTML bridge to LSL in real-time
  - [ ] Handle event types (clicks, markers, custom events, etc.)
  - [ ] Timestamp synchronization between bridge events and LSL
- [ ] **CRITICAL: Integrate LSL stream recording into sessions**
  - [ ] Record LSL streams during session recording
  - [ ] Save LSL stream data to session tracking data
  - [ ] Synchronize LSL streams with session timeline
  - [ ] Support multiple LSL streams (bridge events + hardware devices)

## 6. Session Review & Analysis Interface

- [ ] Create session review window
- [ ] Implement video playback with controls
  - [ ] Play, pause, seek, speed controls
  - [ ] Frame-by-frame navigation
- [ ] Add tracking data overlay system
  - [ ] Mouse position visualization
  - [ ] Future: eye tracking, heart rate, EDA overlays
- [ ] Implement custom event marker system
  - [ ] Add/remove markers during playback
  - [ ] Marker categorization and labeling
  - [ ] Marker export functionality

## 7. Data Visualization & Overlays

- [ ] Design overlay rendering system
  - [ ] Mouse cursor visualization
  - [ ] Click event indicators
  - [ ] Movement trails and heatmaps
- [ ] Implement time-series charts
  - [ ] Mouse position over time
  - [ ] Future: heart rate, EDA, eye tracking data
- [ ] Add event marker visualization
  - [ ] Timeline with marker indicators
  - [ ] Marker details on hover/click

## 8. Export & Data Management

- [ ] Implement session data export
  - [ ] JSON export with all tracking data
  - [ ] CSV export for analysis tools
  - [ ] Video export with overlays
- [ ] Add project dataset export
  - [ ] Combine multiple sessions
  - [ ] Aggregate statistics and summaries
  - [ ] Batch export functionality

## 9. Technical Infrastructure

- [ ] Set up data models and structures
  - [ ] Project data classes
  - [ ] Session data classes
  - [ ] Tracking data classes
- [ ] Implement data persistence layer
  - [ ] File-based storage system
  - [ ] Data validation and integrity
- [ ] Add configuration management
  - [ ] User preferences
  - [ ] Recording settings
  - [ ] Export options

## 10. Future Hardware Integration Preparation

- [ ] Design extensible tracking interface
  - [ ] Abstract tracking device classes
  - [ ] Plugin system for new devices
  - [ ] Data format standardization
- [ ] **CRITICAL: Implement LSL integration framework**
  - [ ] Stream management (create, start, stop LSL streams)
  - [ ] LSL stream recording during sessions
  - [ ] Data synchronization (timestamps, multiple streams)
  - [ ] Device detection and connection (EmotiBit, Tobii Pro Spark)
  - [ ] **HTML bridge event streaming to LSL** (required for embedded webpage sessions)
  - [ ] LSL stream playback and analysis

## 11. Testing & Quality Assurance

- [ ] Create unit tests for core functionality
- [ ] Implement integration tests for recording pipeline
- [ ] Add GUI testing framework
- [ ] Performance testing for real-time operations
- [ ] Cross-platform compatibility testing

## 12. Documentation & User Experience

- [ ] Create user manual and tutorials
- [ ] Add in-app help system
- [ ] Implement keyboard shortcuts
- [ ] Design intuitive UI/UX patterns
- [ ] Add progress indicators and status messages

---

## Priority Order for Implementation

### Phase 1: Basic GUI structure and project management

### Phase 2: Screen recording and mouse tracking

### Phase 3: Session review and basic overlays

### Phase 4: Advanced visualization and export features

### Phase 5: Future hardware integration preparation
