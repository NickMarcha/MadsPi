# LSL Time Synchronization Analysis

## Current Implementation Review

### What's Working ✓

1. **LSL Streams are Being Created with Proper Metadata**
   - `LSLBridgeStreamer` creates a "MadsPipeline_BridgeEvents" stream with `source_id` set to `session_{session_id}`
   - `LSLMouseTrackingStreamer` creates a "MadsPipeline_MouseTracking" stream with proper channel labels
   - EmotiBit streams are being received with their own source IDs

2. **Timestamps are Being Recorded**
   - Each sample has both `timestamp` (LSL local_clock) and `relative_time` (offset from session start)
   - `session_start_time` is captured at recording start

3. **Data is Being Persistently Stored**
   - LSL data is saved to `lsl_recorded_data.json` with full metadata
   - Stream info is preserved for post-hoc analysis

### Issues Identified ⚠️

#### 1. **Missing Clock Offset Information** (CRITICAL)
- **Problem**: LSL stores clock offset measurements between streams for synchronization, but these are **NOT being recorded**
- **Current**: Only timestamps and relative_time are saved
- **Required**: Clock offset data (`clock_offset` measurements) between each inlet and the local clock
- **Impact**: Cannot properly synchronize EmotiBit timestamps with MadsPipeline streams post-hoc
- **Reference**: LSL docs section "Synchronization Information" - "Out-of-band clock synchronization information that is transmitted along with each data stream"

#### 2. **Missing Synchronization Header Metadata** (IMPORTANT)
- **Problem**: No synchronization descriptor in LSL stream headers
- **Current**: Stream info includes basic metadata but no sync info
- **Required**: Add `<synchronization>` block to each stream header with:
  - `offset_mean`: Mean offset from local clock
  - `offset_rms`: RMS jitter in offset measurements
  - `offset_median`: Median offset
  - `offset_5_centile`, `offset_95_centile`: Confidence bounds
  - `can_drop_samples`: true/false flag
- **Reference**: LSL docs section "Stream Header Synchronization Parameters"
- **Impact**: Post-analysis tools won't know stream sync characteristics

#### 3. **Bridge Events Lack Wall-Clock Timestamps** (MODERATE)
- **Problem**: Bridge events use Python `datetime.now().isoformat()` which is NOT synchronized with LSL clock
- **Current**: `madsBridge.py` line 30: `event_data['timestamp'] = datetime.now().isoformat()`
- **Issue**: Python's `datetime.now()` is in a different clock domain than LSL's `local_clock()`
- **Fix Needed**: Use LSL's `local_clock()` instead, or dual-timestamp (both LSL time + wall clock for reference)

#### 4. **Mouse Tracking Event Type Encoding** (MINOR)
- **Problem**: Event types encoded as floats (0, 1, 2, 3, 4) but not well-documented
- **Current**: `lsl_integration.py` lines 118-127
- **Issue**: Hard to interpret without referring to code; should use string labels in LSL metadata
- **Fix**: Add channel description mapping in stream header

#### 5. **Playback-to-Event Time Misalignment** (MODERATE)
- **Problem**: You mentioned "irregularities between the playback time and the events from the BridgeExampleVideo setup"
- **Likely Cause**: 
  - Session start time calculated from LSL clock, but UI playback time uses recorded video FPS
  - Video frame rate may drift from nominal 30 FPS
  - Mouse tracking timestamps may not align with video timeline
- **Diagnosis Needed**: Compare `relative_time` from LSL data vs. video frame numbers * (1/FPS)

### Comparison with EmotiBit Requirements

The EmotiBit documentation emphasizes using a **LSL marker stream** for time synchronization:
- Default: LSL stream named "DataSyncMarker" with source_id "12345"
- EmotiBit Oscilloscope syncs its local data clock to this marker stream
- Requires **at least 2 markers** during recording to establish reliable synchronization

**Current Gap**: MadsPipeline does NOT generate a dedicated marker stream for EmotiBit to use. The BridgeEvents stream could serve this role, but it's not explicitly configured as a marker stream that EmotiBit is configured to find.

---

## Recommended Fixes (Priority Order)

### HIGH PRIORITY

#### 1. Add Clock Offset Recording
```python
# In LSLRecorder.record_sample()
for i, inlet in enumerate(self.inlets):
    # ... existing code ...
    sample, timestamp = inlet.pull_sample(timeout=0.0)
    
    # ADD THIS:
    clock_offset = inlet.time_correction()  # Get current clock offset
    recorded_sample['clock_offset'] = clock_offset
    recorded_sample['local_time_when_measured'] = local_clock()
```

**Why**: Required for proper post-hoc synchronization of multi-stream data (LSL standard practice)

#### 2. Fix Bridge Events to Use LSL Timestamps
```python
# In madsBridge.py receiveMessage()
from pylsl import local_clock

# Instead of:
event_data['timestamp'] = datetime.now().isoformat()

# Use:
event_data['timestamp'] = local_clock()  # LSL time
event_data['wall_clock'] = datetime.now().isoformat()  # For reference
```

**Why**: Bridge events must be in LSL time domain to be synchronized with EmotiBit and other LSL streams

#### 3. Add Stream Synchronization Headers
```python
# In LSLBridgeStreamer._create_stream() and LSLMouseTrackingStreamer._create_stream()

# Add after creating stream info:
sync_desc = info.desc().append_child("synchronization")
sync_desc.append_child_value("offset_mean", "0.0")  # Local source has no offset
sync_desc.append_child_value("offset_rms", "0.001")  # ~1ms jitter typical
sync_desc.append_child_value("offset_median", "0.0")
sync_desc.append_child_value("offset_5_centile", "-0.002")
sync_desc.append_child_value("offset_95_centile", "0.002")
sync_desc.append_child_value("can_drop_samples", "false")  # Regular sampling
```

**Why**: Allows post-hoc analysis tools to apply proper synchronization algorithms

### MEDIUM PRIORITY

#### 4. Improve Video Playback Timeline Accuracy
- Calculate video frame number from first and last LSL sample timestamps
- Account for video frame rate drift (compare nominal vs. measured)
- Use `relative_time` from LSL as ground truth, not video frame count

#### 5. Create Explicit EmotiBit Marker Stream
- Create a "DataSyncMarker" stream that EmotiBit can find
- Send markers at key events (session start, stimulus changes, session end)
- This is what EmotiBit's oscilloscope is configured to search for

### LOW PRIORITY

#### 6. Improve Mouse Tracking Channel Labels
- Add unit and range information to channel descriptions
- Document event type encoding (0=position, 1=press, 2=release, 3=move, 4=scroll)

---

## Data Structure Improvements

### Current LSL Recorded Data Structure
```json
{
  "session_id": "...",
  "stream_info": [...],
  "session_start_time": 670.123,
  "lsl_samples": [
    {
      "timestamp": 670.456,
      "relative_time": 0.333,
      "stream_name": "...",
      "data": "...",
      "raw_data": "..."
    }
  ]
}
```

### Recommended Enhanced Structure
```json
{
  "session_id": "...",
  "stream_info": [...],
  "session_start_time": 670.123,
  "session_start_wall_clock": "2025-11-13T11:21:55.057770",
  "lsl_clock_reference": {
    "note": "All timestamps in this file use LSL local_clock() - steady_clock since boot",
    "conversion_formula": "wall_clock_time ≈ session_start_wall_clock + (timestamp - session_start_time)"
  },
  "clock_offset_measurements": [
    {
      "stream_name": "EmotiBit_acc_x",
      "measurements": [
        {"timestamp": 670.5, "offset": 0.0025, "rtt": 0.001},
        {"timestamp": 671.5, "offset": 0.0027, "rtt": 0.001}
      ]
    }
  ],
  "lsl_samples": [
    {
      "timestamp": 670.456,
      "relative_time": 0.333,
      "stream_name": "...",
      "stream_index": 0,
      "clock_offset": 0.0026,
      "data": "...",
      "raw_data": "..."
    }
  ]
}
```

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
- [ ] Record clock offset measurements in `LSLRecorder.record_sample()`
- [ ] Fix Bridge events to use `local_clock()` instead of `datetime.now()`
- [ ] Update file format to include `session_start_wall_clock` and `lsl_clock_reference`

### Phase 2: Metadata Improvements (Week 2)
- [ ] Add synchronization headers to all LSL streams
- [ ] Improve channel label documentation
- [ ] Add mouse event type descriptions to stream metadata

### Phase 3: Analysis Tools (Week 3)
- [ ] Create post-hoc synchronization function using clock offset data
- [ ] Update SessionReviewWindow to account for clock drifts
- [ ] Validate playback timeline against LSL data

---

## Validation Checklist

After implementing fixes, verify:

- [ ] **Clock Offset**: Verify clock offset measurements are recorded and reasonable (<10ms)
- [ ] **Bridge Events**: Confirm events appear in correct chronological order in plots
- [ ] **EmotiBit Sync**: Test with EmotiBit oscilloscope configured to look for marker stream
- [ ] **Playback Accuracy**: Video frames align with LSL data points within 1 frame
- [ ] **Multi-Stream Alignment**: Events, mouse tracking, and EmotiBit data are properly aligned in graphs

---

## References

- **LSL Time Synchronization**: https://github.com/sccn/labstreaminglayer/wiki/Synchronization
- **EmotiBit LSL Integration**: https://www.emotibit.com/research
- **XDF File Format**: pyxdf library for proper post-hoc analysis
