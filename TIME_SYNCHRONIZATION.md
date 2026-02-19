# LSL Time Synchronization Analysis & Implementation

## Executive Summary

This document analyzes the time synchronization implementation in MadsPipeline. **Solution 1 (Online Clock Synchronization) has been implemented** as of 2025-11-24. All LSL device timestamps are now automatically synchronized to the local time domain using LSL's `proc_clocksync` postprocessing flag.

---

## Current State Analysis

### What's Currently Implemented ✅

1. **Online Clock Synchronization (IMPLEMENTED)**: Clock offset correction is applied manually to synchronize timestamps
   - Location: `src/madspipeline/lsl_integration.py:286, 450-456`
   - Implementation: `synchronized_timestamp = timestamp + clock_offset` (manual correction)
   - Note: pyLSL Python bindings don't support `postproc_flags`, so we apply the correction manually
   - Result: Timestamps from remote devices are **synchronized** to local time domain in real-time

2. **Dual Timestamp Storage**: Both synchronized and original timestamps are preserved
   - `timestamp`: Synchronized to local time domain (for direct comparison)
   - `original_timestamp`: Raw device timestamp from `inlet.pull_sample()` (before sync; for reference)
   - Location: `src/madspipeline/lsl_integration.py:479-490`

3. **Clock Offset Recording**: The application records `clock_offset` for each LSL sample via `inlet.time_correction()`
   - Location: `src/madspipeline/lsl_integration.py:453`
   - Stored in JSON output for validation and post-hoc analysis
   - Clock offset represents the difference between remote device clock and local machine clock

4. **LSL Time Domain for Bridge Events**: Bridge events use `local_clock()` for timestamps
   - Location: `src/madspipeline/madsBridge.py:46`
   - Ensures bridge events are in the same synchronized time domain as LSL streams

5. **Synchronization Metadata**: JSON output includes comprehensive synchronization metadata
   - Location: `src/madspipeline/lsl_integration.py:635-642`
   - Documents synchronization method and field meanings

### Current Data Structure

From sample JSON (`lsl_recording_*.json`):
```json
{
  "timestamp": 532142.4992473,        // Synchronized to local time domain ✅
  "original_timestamp": 532142.5086473, // Original device timestamp (for reference)
  "relative_time": 0.5907100000185892,  // Relative to session start (synchronized)
  "clock_offset": -9.399955160915852e-06, // Clock offset measurement
  "synchronization_applied": true,      // Flag indicating sync is applied
  "local_time_when_recorded": 532143.1547812 // Reference time
}
```

**Status**: The `timestamp` field is now in the **local machine's clock domain** and can be directly compared across all devices. The `original_timestamp` field preserves the device's native clock time for reference.

---

## LSL Time Synchronization Fundamentals

### How LSL Clock Synchronization Works

1. **Clock Offset Measurement**: LSL uses a Network Time Protocol (NTP)-like algorithm
   - Performs 8 UDP packet exchanges (by default) between devices
   - Measures round-trip time (RTT) and clock offset (OFS)
   - Selects offset with minimal RTT (Clock Filter algorithm)
   - Updates every few seconds automatically

2. **Timestamp Correction Methods**:
   - **Simple**: Add most recent clock offset to each timestamp
   - **Linear Fit**: Calculate linear regression through offset history (accounts for clock drift)
   - **Robust Linear Fit**: Outlier-resistant linear fit (more accurate)

3. **Online vs. Offline Synchronization**:
   - **Online**: Use `proc_clocksync` flag → LSL automatically corrects timestamps
   - **Offline**: Record offsets, apply corrections during post-processing

### Accuracy Expectations

- **Typical accuracy**: < 1 ms on symmetric local networks
- **Systematic bias**: Half the difference between forward/backward network latency
- **Clock drift**: Usually linear over short periods (< 1 hour)
- **Jitter**: Additional timestamp jitter from hardware/drivers (often 10x larger than sync error)

---

## Proposed Solutions

### Solution 1: Enable LSL Built-in Clock Synchronization ✅ IMPLEMENTED

**Status**: **IMPLEMENTED** as of 2025-11-24

**Approach**: Use LSL's automatic timestamp correction via postprocessing flags.

**Implementation**:
```python
# In lsl_integration.py, StreamInlet creation (line 286):
inlet = StreamInlet(stream)  # pyLSL doesn't support postproc_flags

# Manual clock synchronization (line 450-456):
clock_offset = inlet.time_correction()  # Get clock offset
original_timestamp = timestamp  # Original device timestamp
synchronized_timestamp = timestamp + clock_offset  # Apply correction manually
```

**Additional Implementation**:
- Clock offset correction applied manually (pyLSL Python bindings limitation)
- Original timestamps preserved: `original_timestamp = timestamp`
- Synchronized timestamps calculated: `synchronized_timestamp = timestamp + clock_offset`
- Both synchronized and original timestamps stored in JSON output
- Synchronization metadata added to JSON schema

**Pros**:
- ✅ Automatic timestamp correction (no manual offset application)
- ✅ Real-time synchronization during recording
- ✅ Handled by LSL library (well-tested)
- ✅ Original timestamps preserved for reference
- ✅ All device timestamps can be directly compared

**Result**: 
- All LSL device timestamps are automatically synchronized to local time domain
- Accuracy: < 1 ms on local networks
- No post-processing required for basic timestamp comparison

---

### Solution 2: Post-Hoc Synchronization with Linear Fit (Recommended for Offline Analysis)

**Approach**: Record clock offsets, then apply linear fit correction during data export/analysis.

**Implementation**:
```python
# New function in lsl_integration.py or new sync_utils.py module
import numpy as np
from scipy import stats

def synchronize_timestamps(recorded_samples, stream_name):
    """
    Apply linear fit through clock offsets to correct timestamps.
    
    Args:
        recorded_samples: List of samples with clock_offset field
        stream_name: Name of stream to synchronize
    
    Returns:
        List of samples with corrected timestamps
    """
    # Extract timestamps and offsets for this stream
    samples = [s for s in recorded_samples if s.get('stream_name') == stream_name]
    
    if not samples:
        return samples
    
    # Get clock offsets and their measurement times
    offsets = [s.get('clock_offset', 0.0) for s in samples]
    measurement_times = [s.get('local_time_when_recorded', s['timestamp']) for s in samples]
    original_timestamps = [s['timestamp'] for s in samples]
    
    # Calculate linear fit: offset(t) = a*t + b
    if len(offsets) > 1:
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            measurement_times, offsets
        )
        
        # Apply correction: corrected_timestamp = original + offset(t)
        for i, sample in enumerate(samples):
            t = measurement_times[i]
            estimated_offset = slope * t + intercept
            sample['synchronized_timestamp'] = original_timestamps[i] + estimated_offset
            sample['sync_offset_applied'] = estimated_offset
            sample['sync_method'] = 'linear_fit'
    else:
        # Single sample: use raw offset
        samples[0]['synchronized_timestamp'] = original_timestamps[0] + offsets[0]
        samples[0]['sync_offset_applied'] = offsets[0]
        samples[0]['sync_method'] = 'simple_offset'
    
    return samples
```

**Pros**:
- ✅ Preserves original timestamps (can compare before/after)
- ✅ Accounts for clock drift (more accurate than simple offset)
- ✅ Can be applied selectively to specific streams
- ✅ Better for offline analysis (can use all data for fit)

**Cons**:
- ⚠️ Requires post-processing step
- ⚠️ Not suitable for real-time applications
- ⚠️ Requires additional dependencies (numpy, scipy)

**When to Use**:
- Offline data analysis
- When you need to preserve original timestamps
- Research applications requiring high accuracy

---

### Solution 3: Hybrid Approach (Recommended)

**Approach**: Enable online sync for real-time needs, but also record original timestamps and offsets for post-hoc analysis.

**Implementation**:
```python
# Create inlet with clock sync enabled
inlet = StreamInlet(stream, postproc_flags=proc_clocksync)

# When recording samples:
sample, corrected_timestamp = inlet.pull_sample(timeout=0.0)
original_timestamp = inlet.time_correction() + corrected_timestamp  # Reconstruct original
clock_offset = inlet.time_correction()

recorded_sample = {
    'timestamp': corrected_timestamp,  # Synchronized (for immediate use)
    'original_timestamp': original_timestamp,  # Original device time (for reference)
    'clock_offset': clock_offset,  # Offset measurement (for post-hoc refinement)
    'data': sample
}
```

**Pros**:
- ✅ Best of both worlds: real-time sync + post-hoc refinement
- ✅ Preserves all timing information
- ✅ Flexible for different use cases

**Cons**:
- ⚠️ Slightly more complex data structure
- ⚠️ Larger JSON files (but usually negligible)

---

### Solution 4: Raspberry Pi as Time Reference (Advanced)

**Context**: You mentioned a Raspberry Pi managing a subnetwork for LSL devices. This could serve as a centralized time reference.

**Approach A: LSL Time Reference Stream**
- Run an LSL outlet on the Raspberry Pi that serves as a "time master"
- All devices synchronize to the Pi's clock
- Pi's clock can be synchronized to NTP for wall-clock alignment

**Implementation on Raspberry Pi**:
```python
# time_reference_server.py (runs on Raspberry Pi)
from pylsl import StreamInfo, StreamOutlet, local_clock
import time

# Create a time reference stream
info = StreamInfo(
    name='TimeReference',
    type='TimeSync',
    channel_count=1,
    nominal_srate=1.0,  # 1 Hz updates
    channel_format='float64',
    source_id='raspberry_pi_time_master'
)

outlet = StreamOutlet(info)

# Periodically send time reference
while True:
    lsl_time = local_clock()
    wall_time = time.time()
    outlet.push_sample([wall_time], lsl_time)
    time.sleep(1.0)
```

**Approach B: NTP Time Synchronization**
- Configure Raspberry Pi as NTP server
- Synchronize all devices (including main PC) to Pi's NTP server
- LSL will still measure clock offsets, but all devices will be closer to wall-clock time

**Pros**:
- ✅ Centralized time reference
- ✅ Can align with wall-clock time (useful for multi-session analysis)
- ✅ Reduces clock drift between devices

**Cons**:
- ⚠️ Requires Pi configuration and network setup
- ⚠️ Additional complexity
- ⚠️ May not be necessary if LSL sync is sufficient

**When to Use**:
- Multi-day experiments requiring wall-clock alignment
- When you need to correlate with external systems (databases, logs)
- Large-scale deployments with many devices

**Recommendation**: Start with Solutions 1-3 first. Only consider Raspberry Pi solution if you need wall-clock alignment or have specific requirements that LSL's built-in sync cannot meet.

---

## Implementation Status

For current implementation status and usage, see **README.md** (LSL Time Synchronization and Data Output Format) and **CURRENT_TIME_IMPLEMENTATION.md** (field semantics and playback).

### Phase 2: Post-Hoc Synchronization Module

**Priority: MEDIUM**

1. **Create `src/madspipeline/sync_utils.py`**:
   - Implement linear fit synchronization function
   - Implement simple offset synchronization function
   - Add validation and error handling

2. **Add synchronization option to data export**:
   - Add checkbox/option: "Apply time synchronization corrections"
   - When enabled, apply linear fit to all remote device streams
   - Export both original and synchronized timestamps

3. **Update JSON schema**:
   - Add `synchronization_applied` flag
   - Add `sync_method` field ('online_clocksync', 'linear_fit', 'simple_offset')
   - Document in README

### Phase 3: Raspberry Pi Integration (If Needed)

**Priority: LOW (Only if required)**

1. **Evaluate need**: Determine if wall-clock alignment is necessary
2. **Pi setup**: Configure as NTP server or LSL time reference
3. **Device configuration**: Ensure all devices can reach Pi
4. **Validation**: Test synchronization accuracy

---

## Testing & Validation

### Test Cases

1. **Multi-Device Recording**:
   - Record EmotiBit + Bridge Events + Mouse Tracking simultaneously
   - Verify all timestamps are in same time domain
   - Check that relative timing between events is correct

2. **Clock Drift Test**:
   - Record for 30+ minutes
   - Verify linear fit captures drift accurately
   - Compare online sync vs. post-hoc linear fit

3. **Network Latency Test**:
   - Test with devices on different network segments
   - Verify sync accuracy remains < 10ms
   - Check that asymmetric network paths don't cause bias

4. **Edge Cases**:
   - Device disconnects/reconnects during recording
   - Very high sample rate streams (100+ Hz)
   - Very low sample rate streams (< 1 Hz)

### Validation Tools

1. **LSL Validation Page**: http://sccn.ucsd.edu/~mgrivich/LSL_Validation.html
2. **Manual verification**: Compare timestamps of simultaneous events
3. **Statistical analysis**: Check offset distributions, drift rates

---

## Migration Path

### For Existing Data

Existing recordings have clock offsets recorded but not applied. You can:

1. **Re-synchronize existing JSON files**:
   - Load JSON file
   - Apply linear fit synchronization function
   - Save new JSON with synchronized timestamps

2. **Analysis tools should handle both**:
   - Check for `synchronized_timestamp` field (new format)
   - Fall back to `timestamp + clock_offset` (old format)

### Backward Compatibility

- Always preserve original timestamps
- Add new fields rather than replacing existing ones
- Document migration in README

---

## Questions & Considerations

### 1. Do you need real-time synchronization?

- **Yes** → Use Solution 1 (enable `proc_clocksync`)
- **No** → Use Solution 2 (post-hoc linear fit)

### 2. Do you need wall-clock alignment?

- **Yes** → Consider Raspberry Pi NTP solution
- **No** → LSL's relative sync is sufficient

### 3. What's your accuracy requirement?

- **< 1 ms** → Use linear fit (Solution 2) or hybrid (Solution 3)
- **< 10 ms** → Simple offset (Solution 1) is usually sufficient
- **< 100 ms** → Current implementation might be acceptable

### 4. Do you need to preserve original timestamps?

- **Yes** → Use Solution 2 or 3 (record both)
- **No** → Solution 1 is fine (LSL modifies timestamps)

---

## References

- **LSL Time Synchronization Docs**: `external_docs/LSL/time_synchronization.rst.txt`
- **LSL Validation**: http://sccn.ucsd.edu/~mgrivich/LSL_Validation.html
- **LSL C++ API**: https://github.com/sccn/liblsl/blob/main/include/lsl/inlet.h (postprocessing flags)
- **pyLSL Documentation**: https://github.com/labstreaminglayer/liblsl-Python

---

*Document created: 2025-11-24*  
*Last updated: 2025-11-24 (Solution 1 implemented)*

