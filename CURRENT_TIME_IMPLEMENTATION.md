# Current Time Implementation in MadsPipeline

## Overview

This document tracks the origin, meaning, and usage of all timestamp fields in MadsPipeline exports and recordings. It explains how timestamps flow from source devices through recording to export and playback.

---

## Timestamp Flow Diagram

```
Source Device/Event
    ↓
[Timestamp Creation]
    ↓
[LSL Recording] → timestamp, original_timestamp, relative_time, clock_offset
    ↓
[Export/JSON] → Same fields preserved
    ↓
[Review Window] → Uses relative_time for playback, calculates video_time
```

---

## Timestamp Sources

### 1. Bridge Events (HTML → Python)

**Source Code**: `src/madspipeline/madsBridge.py:46`

**Timestamp Creation**:
```python
if LSL_AVAILABLE and local_clock:
    event_data['timestamp'] = local_clock()  # LSL synchronized time
    event_data['wall_clock'] = datetime.now().isoformat()  # For reference
```

**Fields Created**:
- `timestamp`: LSL `local_clock()` value (monotonic, boot-relative clock)
- `wall_clock`: Python `datetime.now().isoformat()` (human-readable wall clock time)

**Time Domain**: Local machine's LSL clock (same as all LSL streams)

---

### 2. LSL Device Streams (EmotiBit, etc.)

**Source Code**: `src/madspipeline/lsl_integration.py:400-455`

**Timestamp Creation Process**:
1. **Pull sample from device**: `sample, timestamp = inlet.pull_sample()`
   - `timestamp` is in the **remote device's clock domain**
   
2. **Get clock offset**: `clock_offset = inlet.time_correction()`
   - Measures offset between remote device clock and local machine clock
   - Uses LSL's NTP-like protocol (8 UDP packet exchanges)
   
3. **Apply synchronization**:
   ```python
   original_timestamp = timestamp  # Device's native timestamp
   synchronized_timestamp = timestamp + clock_offset  # Synchronized to local time
   ```

4. **Calculate relative time**:
   ```python
   relative_time = synchronized_timestamp - self.session_start_time
   ```

**Time Domain**: 
- `original_timestamp`: Remote device's clock domain
- `synchronized_timestamp`: Local machine's LSL clock domain (after offset correction)

---

### 3. Video Recording Start

**Source Code**: `src/madspipeline/screen_recorder.py:238`

**Timestamp Creation**:
```python
if LSL_AVAILABLE:
    self.lsl_start_time = local_clock()
```

**Sync Event**:
```python
sync_event = {
    'type': 'video_recording_started',
    'lsl_timestamp': self.lsl_start_time,  # When video recording began
    'session_id': self.session_id,
    'wall_clock': datetime.now().isoformat()
}
```

**Time Domain**: Local machine's LSL clock (same as bridge events)

---

## Timestamp Fields in Recorded Data

### LSL Recording JSON Structure

**Location**: `src/madspipeline/lsl_integration.py:481-495`

Each recorded sample contains:

#### 1. `timestamp` (Synchronized)
- **Type**: `float` (seconds)
- **Source**: `synchronized_timestamp = original_timestamp + clock_offset`
- **Meaning**: Timestamp synchronized to local machine's LSL clock domain
- **Purpose**: **Primary field for comparing timestamps across devices**
- **Time Domain**: Local machine LSL clock (monotonic, boot-relative)
- **Example**: `532142.4992747`

#### 2. `original_timestamp` (Device Native)
- **Type**: `float` (seconds)
- **Source**: `timestamp` from `inlet.pull_sample()` (before synchronization)
- **Meaning**: Original timestamp from the remote device's clock
- **Purpose**: Reference for validation, debugging, or post-hoc analysis
- **Time Domain**: Remote device's clock domain
- **Example**: `532142.4992756` (slightly different from synchronized)
- **Note**: Only present in newer recordings (after synchronization implementation)

#### 3. `relative_time` (Session-Relative)
- **Type**: `float` (seconds)
- **Source**: `synchronized_timestamp - session_start_time`
- **Meaning**: Time elapsed since session recording started
- **Purpose**: **Primary field for playback and timeline visualization**
- **Time Domain**: Relative to session start (starts at 0.0)
- **Example**: `0.5907373999943957` (0.59 seconds after session start)
- **Usage**: Used in review window for playback position

#### 4. `clock_offset` (Synchronization Measurement)
- **Type**: `float` (seconds)
- **Source**: `inlet.time_correction()` - LSL's clock offset measurement
- **Meaning**: Difference between remote device clock and local machine clock
- **Purpose**: For post-hoc synchronization analysis and validation
- **Example**: `-9.399955160915852e-06` (about -9.4 microseconds)
- **Note**: Small values (< 1ms) are typical on local networks

#### 5. `local_time_when_recorded` (Measurement Reference)
- **Type**: `float` (seconds)
- **Source**: `local_clock()` when the sample was recorded
- **Meaning**: Local LSL clock time when the clock offset was measured
- **Purpose**: Reference point for understanding when offset measurement occurred
- **Time Domain**: Local machine LSL clock
- **Example**: `532143.8032856`

#### 6. `synchronization_applied` (Flag)
- **Type**: `boolean`
- **Source**: Always `True` in current implementation
- **Meaning**: Indicates that timestamp synchronization was applied
- **Purpose**: Metadata flag for data analysis tools

---

## Timestamp Fields in Bridge Events (Special Case)

Bridge events have **nested timestamp fields** due to their JSON structure:

### Outer Level (LSL Sample)
- `timestamp`: Synchronized LSL timestamp when event was received by LSL recorder
- `relative_time`: Time relative to session start
- `clock_offset`: Clock offset (usually ~0 for local events)

### Inner Level (Event Data)
- `data.timestamp`: Original LSL timestamp from bridge event creation
- `data.lsl_timestamp`: Duplicate of `data.timestamp` (in sync events)
- `data.wall_clock`: Human-readable wall clock time

**Example from Export**:
```json
{
  "timestamp": 532142.9120417,           // When LSL recorder received the event
  "relative_time": 1.0035044000251219,    // Relative to session start
  "data": {
    "timestamp": 532142.4102643,          // When bridge event was created
    "lsl_timestamp": 532142.4102643,     // Duplicate (in sync events)
    "wall_clock": "2025-11-24T12:51:41.821291"
  }
}
```

**Note**: For bridge events, `data.timestamp` and `data.lsl_timestamp` are **duplicates** - both contain the original event creation time. The outer `timestamp` is when the LSL recorder received it (slightly later).

---

## Timestamp Usage in Review Window

**Source Code**: `src/madspipeline/main_window.py:2653-3786`

### Playback Time Calculation

The review window uses `relative_time` as the primary time reference:

```python
# Current playback position (in seconds from session start)
self.current_time: float = 0.0

# Video offset (for aligning video with events)
self.video_lsl_offset: float = 0.0
```

### Video-Event Alignment

**Process**:
1. **Load video offset** from `screen_recording_info_*.json`:
   - `lsl_first_frame_time`: LSL timestamp of first video frame
   - Converted to relative time: `lsl_first_frame_relative = lsl_first_frame_time - session_start_time`
   - Stored as: `self.video_lsl_offset = lsl_first_frame_relative`

2. **Calculate video time for events**:
   ```python
   video_time = relative_time - video_lsl_offset
   ```
   - If `video_time < 0`: Event occurred before video started (not visible)
   - If `video_time >= 0`: Event occurs at this position in video

3. **Display in events table**:
   - **Video Time column**: Shows `video_time` (mapped to video frames)
   - **LSL Time column**: Shows `relative_time` (original LSL relative time)

### Timeline Slider

- **Position**: Based on `current_time` (in seconds from session start)
- **Range**: 0 to `session_duration`
- **Updates**: Every 100ms during playback
- **Calculation**: `self.current_time += 0.1 * speed`

### Event Highlighting

Events are highlighted based on `relative_time`:
```python
def _highlight_last_event_for_time(self, time: float):
    # Finds event with relative_time closest to current playback time
    for sample in self.lsl_data:
        relative_time = sample.get('relative_time', 0.0)
        if relative_time <= time:
            # Highlight this event
```

---

## Timestamp Fields in Exports

**Source Code**: `src/madspipeline/project_manager.py:601-650`

### Export JSON Structure

Exports preserve all timestamp fields from LSL recordings:

```json
{
  "timestamp": 532142.4992747,           // Synchronized LSL timestamp
  "original_timestamp": 532142.4992756,  // Original device timestamp (if available)
  "relative_time": 0.5907373999943957,   // Time from session start
  "clock_offset": -9.399955160915852e-06, // Clock offset measurement
  "local_time_when_recorded": 532143.8032856, // When offset was measured
  "synchronization_applied": true        // Sync flag
}
```

### CSV Export

CSV exports include:
- `timestamp`: Synchronized timestamp
- `relative_time`: Session-relative time
- `clock_offset`: Clock offset measurement
- `local_time_when_recorded`: Measurement reference time
- `wall_clock`: Human-readable time (for bridge events)

---

## Duplicate Timestamp Fields

### 1. Bridge Events: `data.timestamp` vs `data.lsl_timestamp`

**Location**: Bridge event `data` field

**Duplicates**:
- `data.timestamp`: Original event creation timestamp
- `data.lsl_timestamp`: Same value (duplicate, used in sync events)

**Reason**: Sync events (`video_recording_started`) include `lsl_timestamp` for clarity, but regular events only have `timestamp`.

**Recommendation**: Use `data.timestamp` for consistency. `data.lsl_timestamp` is redundant.

### 2. Outer `timestamp` vs Inner `data.timestamp` (Bridge Events)

**Not duplicates** - different meanings:
- **Outer `timestamp`**: When LSL recorder received the event (slightly later)
- **Inner `data.timestamp`**: When bridge event was created (original time)

**Difference**: Usually < 1ms, but can be larger if LSL recorder is busy.

**Usage**: 
- Use **outer `timestamp`** for chronological ordering with other LSL streams
- Use **inner `data.timestamp`** for event-specific timing (e.g., when user clicked)

---

## Timestamp Comparison Across Devices

### Synchronized Timestamps

All `timestamp` fields (after synchronization) are in the **same time domain**:
- Bridge events: Local LSL clock
- EmotiBit: Local LSL clock (after offset correction)
- Mouse tracking: Local LSL clock
- Video sync events: Local LSL clock

**Result**: Timestamps can be **directly compared** across all devices.

### Example Comparison

```json
// Bridge event
{
  "timestamp": 532142.9120417,      // Synchronized
  "relative_time": 1.0035044
}

// EmotiBit sample (same time period)
{
  "timestamp": 532142.4992747,      // Synchronized (can compare directly)
  "relative_time": 0.5907374
}
```

**Note**: The `timestamp` values are different because they occurred at different absolute times, but they're in the same time domain and can be compared.

---

## Time Domain Reference

### LSL `local_clock()`

**Type**: Monotonic clock (steady, boot-relative)
- **Not wall clock**: No relationship to human calendar time
- **Monotonic**: Always increases, never goes backward
- **Boot-relative**: Counts from system boot (on some platforms)
- **Purpose**: Precise relative timing, not absolute time

**Source**: `std::chrono::steady_clock` (C++ implementation)

**Accuracy**: Sub-millisecond precision

### Session Start Time

**Source**: `self.session_start_time = local_clock()` when recording starts

**Purpose**: Reference point for calculating `relative_time`

**Storage**: Stored in LSL recording JSON as `session_start_time`

---

## Playback Time Calculation Summary

### Review Window Playback

1. **Current Playback Time**: `self.current_time` (seconds from session start)
   - Based on `relative_time` from LSL samples
   - Updated every 100ms during playback

2. **Video Alignment**: `video_time = relative_time - video_lsl_offset`
   - `video_lsl_offset`: Time when video recording started (relative to session)
   - Negative values = before video started (not visible)
   - Positive values = position in video

3. **Event Display**: Events shown with both:
   - **Video Time**: Mapped to video frame position
   - **LSL Time**: Original `relative_time` value

### Timeline Visualization

- **X-axis**: `relative_time` (0 to `session_duration`)
- **Y-axis**: Data values (sensor readings, events)
- **Playback indicator**: Vertical line at `current_time`

---

## Key Takeaways

1. **Primary Timestamp Fields**:
   - `timestamp`: Synchronized, for cross-device comparison
   - `relative_time`: Session-relative, for playback and visualization
   - `original_timestamp`: Device-native, for reference

2. **Synchronization**:
   - All device timestamps are synchronized to local LSL clock
   - Clock offset is measured and applied: `synchronized = original + offset`
   - Accuracy: < 1ms on local networks

3. **Playback**:
   - Uses `relative_time` as primary time reference
   - Video alignment via `video_lsl_offset`
   - Timeline based on session-relative time (0 to duration)

4. **Duplicates**:
   - Bridge events have `data.timestamp` and `data.lsl_timestamp` (use `data.timestamp`)
   - Outer and inner timestamps differ slightly (outer = received time, inner = creation time)

5. **Time Domains**:
   - **LSL timestamps**: Monotonic clock (boot-relative, not wall clock)
   - **Relative time**: Session-relative (starts at 0.0)
   - **Wall clock**: Human-readable time (for reference only)

---

## References

- **LSL Time Synchronization**: `external_docs/LSL/time_synchronization.rst.txt`
- **Time Synchronization Implementation**: `TIME_SYNCHRONIZATION.md`
- **Source Code**:
  - `src/madspipeline/lsl_integration.py` (timestamp creation)
  - `src/madspipeline/madsBridge.py` (bridge event timestamps)
  - `src/madspipeline/main_window.py` (review window playback)
  - `src/madspipeline/project_manager.py` (export formatting)

---

*Document created: 2025-12-03*  
*Last updated: 2025-12-03*

