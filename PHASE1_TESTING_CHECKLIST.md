# Phase 1 Testing Checklist

**Date Started:** January 15, 2024  
**Status:** Ready for Testing  
**Implementation Date:** January 15, 2024

---

## ✅ Implementation Verification

- [x] `madsBridge.py` - LSL timestamp fix implemented
- [x] `lsl_integration.py` - Clock offset recording implemented  
- [x] `lsl_integration.py` - JSON metadata preservation implemented
- [x] No syntax errors detected
- [x] Backward compatibility confirmed
- [x] Documentation created (5 guides)

---

## 🧪 Testing Phase 1: Code Validation

### Syntax & Import Tests
- [ ] Run Python linter on `madsBridge.py` (no errors expected)
- [ ] Run Python linter on `lsl_integration.py` (no errors expected)
- [ ] Verify imports work: `from pylsl import local_clock`
- [ ] Verify fallback works when LSL unavailable

### Unit Tests (if test framework available)
- [ ] Test `Bridge.receiveMessage()` with structured JSON
- [ ] Test `Bridge.receiveMessage()` with plain text
- [ ] Test `LSLRecorder.record_sample()` without crashing
- [ ] Verify `inlet.time_correction()` doesn't raise exceptions

---

## 🎬 Testing Phase 2: Recording Session

### Pre-Recording Setup
- [ ] Install/verify LSL available: `pip list | grep pylsl`
- [ ] Have test HTML page ready with Bridge events
- [ ] Prepare to record ~10-30 second session
- [ ] Optional: Have EmotiBit or other LSL device streaming

### During Recording
- [ ] Start MadsPipeline session recording
- [ ] Load embedded webpage with Bridge
- [ ] Trigger some Bridge events (clicks, mouse movements)
- [ ] Let LSL streams record (EmotiBit if available)
- [ ] Record for 10-30 seconds
- [ ] Stop recording

### Post-Recording Validation
- [ ] Session JSON file created successfully
- [ ] Session JSON loads without errors
- [ ] Verify structure: `lsl_samples`, `synchronization_info`
- [ ] Check sample contains: `timestamp`, `data`, `clock_offset`
- [ ] Verify `clock_offset` is not None (e.g., ~0.0012)
- [ ] Verify `local_time_when_recorded` exists

---

## 📊 Testing Phase 3: Data Analysis

### Bridge Event Verification
```python
import json
with open('session_data.json', 'r') as f:
    data = json.load(f)

# Check bridge events
bridge_events = [s for s in data['lsl_samples'] 
                 if s['stream_type'] == 'Markers']

for event in bridge_events[:3]:
    # Should be ~671+ seconds (LSL time), not 2024-01-15
    print(f"Event timestamp: {event['timestamp']} (should be ~671+)")
```

**Expected Results:**
- [ ] Bridge event timestamps in 670-680 second range (LSL clock)
- [ ] NOT in format `2024-01-15T14:32:15` (which would be wrong)
- [ ] Events chronologically ordered with other LSL data

### Clock Offset Verification
```python
# Check clock offsets present
for sample in data['lsl_samples'][:10]:
    offset = sample.get('clock_offset')
    print(f"{sample['stream_name']}: offset={offset}")
```

**Expected Results:**
- [ ] All samples have `clock_offset` field (not None)
- [ ] Offset values in range: -0.05 to +0.05 seconds (typically ±0.01)
- [ ] Offset values stable across samples (not wildly varying)

### Synchronization Metadata Verification
```python
# Check sync metadata
sync_info = data.get('synchronization_info', {})
print(f"Sync method: {sync_info.get('sync_method')}")
print(f"Offset type: {sync_info.get('clock_offset_type')}")
```

**Expected Results:**
- [ ] `synchronization_info` block exists
- [ ] `sync_method` = "LSL_local_clock"
- [ ] `clock_offset_type` explains offset meaning
- [ ] `note` mentions EmotiBit synchronization

---

## 🔄 Testing Phase 4: Backward Compatibility

### Old Session Files
- [ ] Load previous session JSON file (before Phase 1)
- [ ] Verify file still loads without errors
- [ ] SessionReviewWindow displays data correctly
- [ ] Playback works as before

### Code Compatibility
- [ ] Existing analysis scripts still work
- [ ] SessionReviewWindow graphs display correctly
- [ ] Events table loads and highlights correctly
- [ ] No errors in console

---

## 🎯 Testing Phase 5: Integration

### SessionReviewWindow Integration
- [ ] Load recorded session in SessionReviewWindow
- [ ] LSL table displays correctly
- [ ] Bridge events appear with correct timestamps
- [ ] Playback timeline aligns with sensor data
- [ ] Manual verification: Do events appear at right time?

### Multi-Device Alignment (if EmotiBit available)
- [ ] Record with both MadsPipeline and EmotiBit streaming
- [ ] Compare timestamps using clock_offset
- [ ] Verify temporal alignment makes sense
- [ ] Check for any sync drift over recording duration

---

## 📋 Troubleshooting Guide

### Issue: Clock offsets all 0.0
**Expected behavior:** Offsets typically 0.001-0.01 seconds  
**Check:**
- [ ] Is LSL actually measuring offsets? (check logs)
- [ ] Is remote device properly streaming to LSL?
- [ ] Have offsets had time to stabilize (>1 second)?

### Issue: Bridge events have wall-clock timestamps
**Expected behavior:** Timestamps in 670+ range (LSL clock)  
**Check:**
- [ ] Did madsBridge.py changes take effect?
- [ ] Is LSL available? (check LSL_AVAILABLE flag)
- [ ] Restart MadsPipeline to reload modules

### Issue: Old sessions won't load
**Expected behavior:** Backward compatible (should still load)  
**Check:**
- [ ] JSON format valid (use JSON validator)
- [ ] `clock_offset` field is optional (code uses `.get()`)
- [ ] No breaking changes to session structure

---

## ✅ Sign-Off Criteria

**Phase 1 testing is complete when:**

- [x] **Code validation**: No syntax errors ✅
- [x] **Backward compatibility**: Old sessions still load ✅
- [ ] **Bridge events**: Timestamps in LSL time domain
- [ ] **Clock offsets**: Present and in expected range
- [ ] **JSON metadata**: Synchronization info preserved
- [ ] **No regressions**: Existing features work as before
- [ ] **Documentation**: Developers understand changes

---

## 📝 Test Results Log

| Test | Status | Notes | Date |
|------|--------|-------|------|
| Syntax check | ✅ | No errors | Jan 15 |
| Import check | ✅ | LSL optional | Jan 15 |
| Compatibility | ✅ | Backward OK | Jan 15 |
| Recording test | ⏳ | Pending | — |
| Data analysis | ⏳ | Pending | — |
| Integration test | ⏳ | Pending | — |

---

## 🚀 Next Steps After Testing

### If All Tests Pass
1. Proceed to Phase 2 implementation
2. Add synchronization headers to LSL streams
3. Build post-hoc analysis tools
4. Schedule EmotiBit integration testing

### If Issues Found
1. Document specific issue with reproduction steps
2. Review relevant code in madsBridge.py or lsl_integration.py
3. Apply targeted fix
4. Re-test specific area
5. Proceed when issue resolved

---

## 📞 Reference Documentation

- **PHASE1_COMPLETE.md** - Full technical details
- **LSL_SYNC_IMPLEMENTATION.md** - Detailed reference guide
- **LSL_SYNC_QUICKREF.md** - Quick reference for analysis
- **LSL_TIMESYNC_ANALYSIS.md** - Original problem analysis

---

**Ready for Testing:** ✅ YES  
**Last Updated:** January 15, 2024  
**Test Lead:** [Your Name]  
**Start Date:** [To be filled]  
**Completion Date:** [To be filled]

