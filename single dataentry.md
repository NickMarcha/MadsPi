Single data entry explanation

## EmotiBit Sample Entry

```json
{
    "timestamp": 11484.943603750002,                  // Synchronized LSL timestamp (for cross-device comparison)
    "original_timestamp": 11484.9436241,              // Original device timestamp (before synchronization)
    "relative_time": 91.56823495000208,               // Time since recording started (seconds from session_start_time)
    "stream_name": "EmotiBit_BrainFlow",
    "stream_type": "EmotiBit",
    "data": [                                         // Filtered data array (only selected channels)
        50507.0,                                      // data[0] = Temperature (see channel_labels["0"])
        0.24300000071525574,                          // data[1] = Humidity (see channel_labels["1"])
        -0.23999999463558197,                         // data[2] = EDA (see channel_labels["2"])
        -1.0809999704360962,                          // data[3] = PPG_IR (see channel_labels["3"])
        -9.277000427246094,                           // data[4] = PPG_Red (see channel_labels["4"])
        8.392000198364258                             // data[5] = PPG_Green (see channel_labels["5"])
    ],
    "raw_data": [                                     // Raw data array (same as data for numeric streams)
        50507.0,
        0.24300000071525574,
        -0.23999999463558197,
        -1.0809999704360962,
        -9.277000427246094,
        8.392000198364258
    ],
    "clock_offset": -2.0349999431346077e-05,          // LSL clock offset measurement (device clock - local clock) at this moment
    "local_time_when_recorded": 11484.9960957,        // Local LSL time when clock offset was measured
    "linear_fit_offset": -1.145554212761944e-05,      // Clock offset calculated from linear fit (accounts for clock drift, more accurate)
    "synchronization_applied": true                   // Flag indicating timestamp synchronization is active
}
```

### Clock Offset vs Linear Fit Offset

**Two offset fields are provided for different use cases:**

1. **`clock_offset`** (Raw Measurement):
   - The actual clock offset measured by LSL at this specific moment
   - Direct measurement from `inlet.time_correction()`
   - Use when you need the exact offset at that instant
   - Can be noisy due to network jitter

2. **`linear_fit_offset`** (Smoothed Estimate):
   - Calculated from a linear fit through all clock offset measurements in the session
   - Formula: `offset(t) = slope * time + intercept` (see `stream_info["clock_sync_linear_fit"]`)
   - Accounts for clock drift over time (more accurate for longer recordings)
   - Smoothes out measurement noise
   - **Recommended for most analysis** as it's more accurate

**Linear Fit Parameters** (stored in `stream_info["clock_sync_linear_fit"]`):
```json
{
    "slope": -3.788948325185762e-08,        // Rate of clock drift (seconds per second)
    "intercept": 0.0004237035036472227,     // Initial offset at t=0
    "r_squared": 0.009814991711005527,      // Fit quality (0-1, higher is better)
    "std_err": 1.1453716390782549e-05,      // Standard error of the fit
    "n_points": 2630,                       // Number of offset measurements used
    "formula": "offset(t) = -3.79e-08 * t + 4.24e-04"
}
```

**When to use which:**
- **Use `clock_offset`**: For real-time applications, or when you need the exact measurement at that moment
- **Use `linear_fit_offset`**: For offline analysis, longer recordings, or when you need the most accurate synchronization (accounts for drift)

**Note**: The `timestamp` field uses `clock_offset` (simple approach). For improved accuracy, you can recalculate: `synchronized_timestamp = original_timestamp + linear_fit_offset`

### Channel Mapping (Important: Filtered Channels)

**Channel information is stored in `stream_info` at the top of the export file.** The session now stores complete channel mapping information, so you don't need to check project settings.

**Stream Info Structure:**
```json
{
    "name": "EmotiBit_BrainFlow",
    "type": "EmotiBit",
    "channel_count": 6,                               // Number of channels actually recorded
    "original_channel_count": 12,                     // Total channels available in the stream
    "channel_labels": {                                // Only labels for RECORDED channels
        "0": "Temperature",                            // Maps to data[0]
        "1": "Humidity",                               // Maps to data[1]
        "2": "EDA",                                    // Maps to data[2]
        "3": "PPG_IR",                                 // Maps to data[3]
        "4": "PPG_Red",                                // Maps to data[4]
        "5": "PPG_Green"                               // Maps to data[5]
    },
    "filtered_channel_indices": [                     // Original channel indices that were recorded
        0,                                             // data[0] came from original channel 0
        1,                                             // data[1] came from original channel 1
        2,                                             // data[2] came from original channel 2
        3,                                             // data[3] came from original channel 3
        4,                                             // data[4] came from original channel 4
        5                                              // data[5] came from original channel 5
    ]
}
```

**Understanding Channel Filtering:**

1. **Stream has 12 channels total** (`original_channel_count: 12`):
   - Original channels 0-5: Temperature, Humidity, EDA, PPG_IR, PPG_Red, PPG_Green
   - Original channels 6-11: Accel_X, Accel_Y, Accel_Z, Gyro_X, Gyro_Y, Gyro_Z

2. **Only 6 channels were recorded** (`channel_count: 6`):
   - The `data` array contains **only the filtered channels** in order
   - `channel_labels` shows **only the recorded channels** (keys "0" through "5" match data array indices)
   - `filtered_channel_indices` shows which original channels were recorded: [0, 1, 2, 3, 4, 5]

3. **Direct Mapping:**
   - `data[0]` = `channel_labels["0"]` = "Temperature" (from original channel 0)
   - `data[1]` = `channel_labels["1"]` = "Humidity" (from original channel 1)
   - `data[2]` = `channel_labels["2"]` = "EDA" (from original channel 2)
   - And so on...

4. **Channels 6-11 are NOT in the data array** because they were filtered out during recording.

**Mapping Process:**
1. Find `stream_info` entry matching `stream_name: "EmotiBit_BrainFlow"`
2. Use `channel_labels` to map data array indices to channel names (keys match data indices)
3. Use `filtered_channel_indices` if you need to know which original channel numbers were recorded
4. Use `original_channel_count` to see how many total channels were available

**Note:** If channels are skipped (e.g., recording only channels [0, 2, 5]), the `data` array will contain 3 values, `channel_labels` will have keys "0", "1", "2", and `filtered_channel_indices` will be [0, 2, 5] showing which original channels they represent.

### Data vs Raw Data

**For numeric streams (EmotiBit, sensors):**
- `data` and `raw_data` are **identical** - both contain the same numeric array
- No processing is applied to numeric streams

**For marker streams (Bridge Events):**
- `data`: Parsed JSON object (structured, easy to access)
- `raw_data`: Original string representation (for reference/debugging)

---

## Bridge Event (Marker) Entry

```json
{
    "timestamp": 11485.00389485,                     // When LSL recorder RECEIVED the event (slightly later)
    "original_timestamp": 11485.0038996,              // Original timestamp (before synchronization)
    "relative_time": 91.6285260500008,               // Time since recording started
    "stream_name": "MadsPipeline_BridgeEvents",
    "stream_type": "Markers",
    "data": {                                        // Parsed JSON object (structured)
        "data": {
            "step": 4,
            "timestamp": 1764768348428               // JavaScript timestamp (milliseconds since epoch)
        },
        "timestamp": 11485.0037656,                  // When bridge event was CREATED (original LSL time)
        "type": "step_change",
        "wall_clock": "2025-12-03T14:25:48.428496"  // Human-readable wall clock time
    },
    "raw_data": [                                    // Original string (for reference)
        "{\"data\": {\"step\": 4, \"timestamp\": 1764768348428}, \"timestamp\": 11485.0037656, \"type\": \"step_change\", \"wall_clock\": \"2025-12-03T14:25:48.428496\"}"
    ],
    "clock_offset": -4.749999789055437e-06,          // Clock offset (usually small for local events)
    "local_time_when_recorded": 11485.0159727,       // When offset was measured
    "synchronization_applied": true                   // Flag indicating timestamp synchronization is active
}
```

### Understanding Nested Timestamps in Bridge Events

Bridge events have **multiple timestamps** because they pass through multiple stages:

1. **Outer `timestamp`** (532149.0113554): 
   - When the LSL recorder **received** the event
   - Slightly later than creation (processing delay)
   - Use this for chronological ordering with other LSL streams

2. **Inner `data.timestamp`** (532149.0112505):
   - When the bridge event was **originally created** (in JavaScript/Python)
   - More accurate for event-specific timing (e.g., when user clicked)
   - Difference from outer timestamp: ~0.1ms (processing delay)

3. **Inner `data.data.timestamp`** (1763985108421):
   - JavaScript timestamp in **milliseconds** (different time domain!)
   - From the web page/JavaScript side
   - Not synchronized with LSL time - use for reference only

4. **`data.wall_clock`** ("2025-11-24T12:51:48.422236"):
   - Human-readable wall clock time
   - For reference/debugging only

### Why the Difference?

- **Outer timestamp** = When LSL recorder processed the event (slightly later)
- **Inner timestamp** = When the event was originally created (more accurate for event timing)
- **Difference**: Usually < 1ms, but can be larger if LSL recorder is busy

**Recommendation**: Use **outer `timestamp`** for comparing with other LSL streams, use **inner `data.timestamp`** for event-specific timing.

---

## Notes

- **`original_timestamp`**: Present in exports from **November 2025 onwards** (after synchronization implementation). Older exports won't have this field.
- **`linear_fit_offset`**: Present in exports from **December 2025 onwards** (after linear fit implementation). Calculated during export for both new and existing recordings. If not present, use `clock_offset` instead. See "Clock Offset vs Linear Fit Offset" section above for details.
- **Channel filtering**: The `channel_labels` in `stream_info` now shows **only the channels that were recorded**, not all available channels. The keys ("0", "1", "2", ...) match the `data` array indices directly. Use `filtered_channel_indices` to see which original channel numbers were recorded, and `original_channel_count` to see how many total channels were available in the stream.
- **Session stores channel info**: All channel mapping information is stored in the session/export files. You don't need to check project settings - the `stream_info` contains everything you need.
- **Data vs Raw Data**: For numeric streams they're identical; for markers, `data` is parsed JSON and `raw_data` is the original string.
- **No recording fault**: If you see 6 channels in the data and 6 in channel_labels (but 12 in original_channel_count), this is normal - it means channel filtering was applied during recording. Only the selected channels (0-5 in this example) were recorded.
- **Clock synchronization**: The `timestamp` field uses simple offset correction (`original_timestamp + clock_offset`). For improved accuracy, especially in longer recordings, consider using `linear_fit_offset` which accounts for clock drift.