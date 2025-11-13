# Quick Reference: LSL Synchronization Fixes

## ✅ What Was Fixed

### 1. Bridge Events Now Use LSL Time
**File:** `src/madspipeline/madsBridge.py`  
**What changed:** `datetime.now()` → `local_clock()`

```python
# OLD: ❌ Wrong time domain
event_data['timestamp'] = datetime.now().isoformat()  # Wall clock

# NEW: ✅ Correct time domain
event_data['timestamp'] = local_clock()  # LSL steady clock
event_data['wall_clock'] = datetime.now().isoformat()  # Preserved for reference
```

**Why it matters:** Bridge events now align chronologically with LSL streams (EmotiBit, sensors, etc.)

---

### 2. LSL Samples Now Include Clock Offsets
**File:** `src/madspipeline/lsl_integration.py` (LSLRecorder class)  
**What changed:** Added `clock_offset` measurement to every recorded sample

```python
# NEW: Measure the offset between local and remote clocks
clock_offset = inlet.time_correction()  # Returns seconds

# Store it with the sample
recorded_sample['clock_offset'] = clock_offset
recorded_sample['local_time_when_recorded'] = local_clock()
```

**Why it matters:** Enables post-hoc synchronization with EmotiBit and other LSL-streaming devices

---

### 3. Session JSON Files Now Preserve Synchronization Data
**File:** `src/madspipeline/lsl_integration.py` (save_to_file method)  
**What changed:** Each saved sample now includes sync metadata

```json
{
  "timestamp": 671.234,
  "stream_name": "EDA",
  "data": [1.23],
  "clock_offset": 0.0012,
  "local_time_when_recorded": 671.2341
}
```

**Why it matters:** Analysis tools can access synchronization data without re-running recordings

---

## 🎯 How to Use These Changes

### Recording Sessions (No code changes needed)
1. Start a normal MadsPipeline session
2. Use HTML bridge for events
3. Connect EmotiBit or other LSL device
4. Recording automatically captures:
   - ✅ Bridge events with LSL timestamps
   - ✅ Clock offsets for every LSL sample
   - ✅ Synchronization metadata in JSON

### Analyzing Sessions (Python)
```python
import json

# Load session data
with open('session_data.json', 'r') as f:
    data = json.load(f)

# Access synchronization info
sync_info = data['synchronization_info']
print(f"Sync method: {sync_info['sync_method']}")

# Get clock offsets
for sample in data['lsl_samples']:
    if sample['stream_name'] == 'EDA':
        print(f"EDA offset: {sample['clock_offset']} seconds")
        print(f"Timestamp: {sample['timestamp']}")
```

### Aligning Multiple Streams (Python)
```python
# Get EmotiBit stream
emotib_samples = [s for s in data['lsl_samples'] if 'EDA' in s['stream_name']]

# Get Bridge events
bridge_events = [s for s in data['lsl_samples'] if s['stream_type'] == 'Markers']

# Create aligned timeline using clock offsets
for event in bridge_events:
    event_time_lsl = event['timestamp']
    
    # Find nearest EmotiBit sample
    emotib_times = [s['timestamp'] + s['clock_offset'] for s in emotib_samples]
    nearest = min(emotib_times, key=lambda t: abs(t - event_time_lsl))
    
    print(f"Event at {event_time_lsl}: nearest sensor at {nearest}")
```

---

## 📊 Expected Results

### Before Fixes
```
Bridge events:        2024-01-15T14:32:15.123  (wall clock)
LSL samples:          671.234 seconds          (LSL clock)
                      ❌ Cannot correlate
```

### After Fixes
```
Bridge events:        671.345 seconds          (LSL clock)  ✅
LSL samples:          671.234 seconds          (LSL clock)  ✅
Clock offsets:        [0.0012, -0.0008, ...]   (per sample) ✅
                      ✅ Everything aligns!
```

---

## ⚠️ Important Notes

1. **Clock offsets are small** (~1-5 milliseconds)
   - This is normal for LSL synchronized devices
   - Used for high-precision post-hoc alignment

2. **Wall clock preserved**
   - `event_data['wall_clock']` still stores original datetime
   - Use for human-readable timestamps

3. **Backward compatible**
   - Old session files still load (clock_offset will be None)
   - No breaking changes to API

4. **LSL must be available**
   - Falls back gracefully if LSL not installed
   - Uses regular timestamps if LSL import fails

---

## 🔍 Verification Checklist

- [ ] madsBridge.py imports `local_clock` successfully
- [ ] LSLRecorder calls `inlet.time_correction()` for each sample
- [ ] Session JSON files include `clock_offset` fields
- [ ] `synchronization_info` appears in saved session metadata
- [ ] Bridge events display in chronological order with sensor data

---

## 🚀 Next Phase (Phase 2)

- Add synchronization headers to LSL stream metadata
- Create post-hoc synchronization analysis tools
- Build visualization for clock offset trajectories
- Integrate with EmotiBit Oscilloscope format

**Status:** Phase 1 Complete ✅  
**Test Date:** Ready for immediate validation  
**Documentation:** Full details in LSL_SYNC_IMPLEMENTATION.md
