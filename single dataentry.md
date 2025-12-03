Single data entry explanation

## EmotiBit Sample Entry

```json
{
    "timestamp": 17358.0383437,                       // Synchronized LSL timestamp (for cross-device comparison)
    "original_timestamp": 17358.0383523,             // Original device timestamp (before synchronization)
    "relative_time": 4.573580899999797,              // Time since recording started (seconds from session_start_time)
    "stream_name": "EmotiBit_BrainFlow",
    "stream_type": "EmotiBit",
    "data": [                                         // Filtered data array (only selected channels)
        1.496664047241211,                            // data[0] = EDA (EA) - in microsiemens
        39.016998291015625,                           // data[1] = Temperature (T1) - in degrees Celsius
        37.891998291015625,                           // data[2] = Temperature2 (T2) - in degrees Celsius (second temperature sensor)
        170016.0,                                     // data[3] = PPG_IR (PI) - Raw ADC values
        154335.0,                                     // data[4] = PPG_Red (PR) - Raw ADC values
        13511.0                                       // data[5] = PPG_Green (PG) - Raw ADC values
    ],
    "raw_data": [                                     // Raw data array (same as data for numeric streams)
        1.496664047241211,
        39.016998291015625,
        37.891998291015625,
        170016.0,
        154335.0,
        13511.0
    ],
    "clock_offset": -8.600000001024455e-06,          // LSL clock offset measurement (device clock - local clock) at this moment
    "local_time_when_recorded": 17358.0447723,       // Local LSL time when clock offset was measured
    "linear_fit_offset": -9.64693489451606e-06,     // Clock offset calculated from linear fit (accounts for clock drift, more accurate)
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

### EmotiBit Data Format Notes

**✅ Data Format Fixed**: As of December 2025, the implementation correctly reads from all three BrainFlow presets and combines them with proper channel mapping. Values are now in the expected units.

**Data Source**: The values shown are **exactly as received from BrainFlow** after reading from the appropriate presets:
- **ANCILLARY_PRESET**: Temperature, Humidity, EDA
- **AUXILIARY_PRESET**: PPG (IR, Red, Green)
- **DEFAULT_PRESET**: Motion sensors (Accelerometer, Gyroscope, Magnetometer)

**EDA (EA - Electrodermal Activity)**:
- **Units**: microsiemens
- **Expected range**: Typically 0.1-100 microsiemens (varies by individual and activity)
- **Example value**: `1.497` = 1.50 microsiemens (reasonable value for EDA)
- **Note**: EDA values can vary significantly based on emotional state, stress, and physical activity
- **Channel**: data[0] (first channel from ANCILLARY_PRESET)

**Temperature (T1)**:
- **Units**: degrees Celsius
- **Expected range**: ~30-40°C (body temperature range)
- **Example value**: `39.017` = 39.02°C (normal body temperature)
- **Channel**: data[1] (second channel from ANCILLARY_PRESET)
- **Note**: This is the primary temperature sensor (T1 from MAX30101)

**Temperature2 (T2)**:
- **Units**: degrees Celsius
- **Expected range**: ~30-40°C (body temperature range)
- **Example value**: `37.892` = 37.89°C (second temperature reading)
- **Channel**: data[2] (third channel from ANCILLARY_PRESET)
- **Note**: This may be a second temperature sensor reading. Some EmotiBit devices have `TH` (Thermopile, medical-grade, only on EmotiBit MD) as a separate sensor.

**PPG Channels (PI, PR, PG)**:
- **Units**: Raw ADC values
- **Expected range**: Large positive integers (typically 10,000-200,000)
- **Example values**: 
  - `167788.0` (PPG_IR)
  - `154754.0` (PPG_Red)
  - `13491.0` (PPG_Green)
- These are raw/unprocessed ADC values from the photoplethysmogram sensors

**BrainFlow Presets for EmotiBit:**
The implementation correctly reads from all three presets:
- **ANCILLARY_PRESET**: Temperature (channel 2), Humidity (channel 1), EDA (channel 3)
- **AUXILIARY_PRESET**: PPG_IR (channel 1), PPG_Red (channel 2), PPG_Green (channel 3)
- **DEFAULT_PRESET**: Accelerometer (channels 1-3), Gyroscope (channels 4-6), Magnetometer (channels 7-9)

**Total Available Channels**: 15 channels (3 from ANCILLARY + 3 from AUXILIARY + 9 from DEFAULT)

**References**: 
- `external_docs/EmotiBit/Working_with_emotibit_data.md` - EmotiBit's documented data formats
- `external_docs/brainflow/dataformatdesc.html` - BrainFlow data format description
- `EMOTIBIT_DATA_FORMAT_ISSUE.md` - Documentation of the fix implementation

### Channel Mapping (Important: Filtered Channels)

**Channel information is stored in `stream_info` at the top of the export file.** The session now stores complete channel mapping information, so you don't need to check project settings.

**Stream Info Structure:**
```json
{
    "name": "EmotiBit_BrainFlow",
    "type": "EmotiBit",
    "channel_count": 6,                               // Number of channels actually recorded
    "original_channel_count": 15,                     // Total channels available in the stream
    "channel_labels": {                                // Only labels for RECORDED channels
        "0": "EDA",                                    // Maps to data[0] - from ANCILLARY_PRESET channel 1
        "1": "Temperature",                           // Maps to data[1] - from ANCILLARY_PRESET channel 2
        "2": "Temperature2",                          // Maps to data[2] - from ANCILLARY_PRESET channel 3
        "3": "PPG_IR",                                 // Maps to data[3] - from AUXILIARY_PRESET channel 1
        "4": "PPG_Red",                                // Maps to data[4] - from AUXILIARY_PRESET channel 2
        "5": "PPG_Green"                               // Maps to data[5] - from AUXILIARY_PRESET channel 3
    },
    "filtered_channel_indices": [                     // Original channel indices that were recorded
        0,                                             // data[0] came from original channel 0 (EDA)
        1,                                             // data[1] came from original channel 1 (Temperature)
        2,                                             // data[2] came from original channel 2 (Temperature2)
        3,                                             // data[3] came from original channel 3 (PPG_IR)
        4,                                             // data[4] came from original channel 4 (PPG_Red)
        5                                              // data[5] came from original channel 5 (PPG_Green)
    ]
}
```

**Understanding Channel Filtering:**

1. **Stream has 15 channels total** (`original_channel_count: 15`):
   - Original channels 0-2: EDA, Temperature, Temperature2 (from ANCILLARY_PRESET)
   - Original channels 3-5: PPG_IR, PPG_Red, PPG_Green (from AUXILIARY_PRESET)
   - Original channels 6-14: Accel_X, Accel_Y, Accel_Z, Gyro_X, Gyro_Y, Gyro_Z, Mag_X, Mag_Y, Mag_Z (from DEFAULT_PRESET)

2. **Only 6 channels were recorded** (`channel_count: 6`):
   - The `data` array contains **only the filtered channels** in order
   - `channel_labels` shows **only the recorded channels** (keys "0" through "5" match data array indices)
   - `filtered_channel_indices` shows which original channels were recorded: [0, 1, 2, 3, 4, 5]

3. **Direct Mapping:**
   - `data[0]` = `channel_labels["0"]` = "EDA" (from original channel 0, ANCILLARY_PRESET channel 1)
   - `data[1]` = `channel_labels["1"]` = "Temperature" (from original channel 1, ANCILLARY_PRESET channel 2)
   - `data[2]` = `channel_labels["2"]` = "Temperature2" (from original channel 2, ANCILLARY_PRESET channel 3)
   - `data[3]` = `channel_labels["3"]` = "PPG_IR" (from original channel 3, AUXILIARY_PRESET channel 1)
   - `data[4]` = `channel_labels["4"]` = "PPG_Red" (from original channel 4, AUXILIARY_PRESET channel 2)
   - `data[5]` = `channel_labels["5"]` = "PPG_Green" (from original channel 5, AUXILIARY_PRESET channel 3)

4. **Channels 6-14 are NOT in the data array** because they were filtered out during recording (motion sensors: accelerometer, gyroscope, magnetometer).

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
    "timestamp": 17358.0124364,                      // When LSL recorder RECEIVED the event (slightly later)
    "original_timestamp": 17358.01246,               // Original timestamp (before synchronization)
    "relative_time": 4.547673600001872,              // Time since recording started
    "stream_name": "MadsPipeline_BridgeEvents",
    "stream_type": "Markers",
    "data": {                                        // Parsed JSON object (structured)
        "data": {
            "answer": "good",
            "answer_label": "Good - I can usually maintain focus, but sometimes get distracted",
            "question": "focus_ability",
            "timestamp": 1764774221437               // JavaScript timestamp (milliseconds since epoch)
        },
        "timestamp": 17358.0123682,                  // When bridge event was CREATED (original LSL time)
        "type": "radio_selected",
        "wall_clock": "2025-12-03T16:03:41.437712"  // Human-readable wall clock time
    },
    "raw_data": [                                    // Original string (for reference)
        "{\"data\": {\"answer\": \"good\", \"answer_label\": \"Good - I can usually maintain focus, but sometimes get distracted\", \"question\": \"focus_ability\", \"timestamp\": 1764774221437}, \"timestamp\": 17358.0123682, \"type\": \"radio_selected\", \"wall_clock\": \"2025-12-03T16:03:41.437712\"}"
    ],
    "clock_offset": -2.3599999622092582e-05,        // Clock offset (usually small for local events)
    "local_time_when_recorded": 17358.0251037,      // When offset was measured
    "linear_fit_offset": -4.199365856685745e-06,    // Clock offset calculated from linear fit (accounts for clock drift, more accurate)
    "synchronization_applied": true                   // Flag indicating timestamp synchronization is active
}
```

### Understanding Nested Timestamps in Bridge Events

Bridge events have **multiple timestamps** because they pass through multiple stages:

1. **Outer `timestamp`** (17358.0124364): 
   - When the LSL recorder **received** the event
   - Slightly later than creation (processing delay)
   - Use this for chronological ordering with other LSL streams

2. **Inner `data.timestamp`** (17358.0123682):
   - When the bridge event was **originally created** (in JavaScript/Python)
   - More accurate for event-specific timing (e.g., when user clicked)
   - Difference from outer timestamp: ~0.07ms (processing delay)

3. **Inner `data.data.timestamp`** (1764774221437):
   - JavaScript timestamp in **milliseconds** (different time domain!)
   - From the web page/JavaScript side
   - Not synchronized with LSL time - use for reference only

4. **`data.wall_clock`** ("2025-12-03T16:03:41.437712"):
   - Human-readable wall clock time
   - For reference/debugging only

### Why the Difference?

- **Outer timestamp** = When LSL recorder processed the event (slightly later)
- **Inner timestamp** = When the event was originally created (more accurate for event timing)
- **Difference**: Usually < 1ms, but can be larger if LSL recorder is busy

**Recommendation**: Use **outer `timestamp`** for comparing with other LSL streams, use **inner `data.timestamp`** for event-specific timing.

---

## CSV Export Format

**CSV export is a flattened version of the JSON data** with the following flattening rules:

### Top-Level Fields
All top-level fields from JSON samples become CSV columns directly:
- `timestamp`, `original_timestamp`, `relative_time`
- `stream_name`, `stream_type`
- `clock_offset`, `local_time_when_recorded`, `linear_fit_offset`
- `session_id`, `session_name` (added during export)

### Data Field Flattening

**For Numeric Arrays (EmotiBit, Mouse Tracking, etc.):**
- **1 value**: Stored in `data_value` column
- **2 values**: Stored in `data_x`, `data_y` columns
- **3 values**: Stored in `data_x`, `data_y`, `data_z` columns
- **4+ values**: Stored as JSON string in `data_array` column
  - Example: EmotiBit with 6 channels → `data_array` = `"[1.497, 39.017, 37.892, 170016.0, 154335.0, 13511.0]"`

**For Bridge Events (Nested JSON):**
- Top-level event fields: `event_type`, `wall_clock`
- Nested `data` object: Flattened with `data_` prefix
  - Example: `data.answer` → `data_answer` column
  - Example: `data.data.timestamp` → `data_data_timestamp` column
- Recursively nested objects: Flattened with underscore separators
  - Example: `data.data.question` → `data_data_question` column

### Example CSV Row (EmotiBit)

```csv
session_id,session_name,timestamp,original_timestamp,relative_time,stream_name,stream_type,clock_offset,local_time_when_recorded,linear_fit_offset,data_array
20251203_160333_696341,final4,17358.0383437,17358.0383523,4.573580899999797,EmotiBit_BrainFlow,EmotiBit,-8.600000001024455e-06,17358.0447723,-9.64693489451606e-06,"[1.496664047241211, 39.016998291015625, 37.891998291015625, 170016.0, 154335.0, 13511.0]"
```

### Example CSV Row (Bridge Event)

```csv
session_id,session_name,timestamp,original_timestamp,relative_time,stream_name,stream_type,clock_offset,local_time_when_recorded,linear_fit_offset,event_type,wall_clock,data_answer,data_answer_label,data_question,data_data_timestamp,data_timestamp
20251203_160333_696341,final4,17358.0124364,17358.01246,4.547673600001872,MadsPipeline_BridgeEvents,Markers,-2.3599999622092582e-05,17358.0251037,-4.199365856685745e-06,radio_selected,2025-12-03T16:03:41.437712,good,"Good - I can usually maintain focus, but sometimes get distracted",focus_ability,1764774221437,17358.0123682
```

**Note**: For multi-channel numeric data (like EmotiBit with 6 channels), the array is stored as a JSON string in the `data_array` column. You can parse this in your analysis tool (e.g., `json.loads()` in Python, `JSON.parse()` in JavaScript) to access individual channel values.

---

## Notes

- **`original_timestamp`**: Present in exports from **November 2025 onwards** (after synchronization implementation). Older exports won't have this field.
- **`linear_fit_offset`**: Present in exports from **December 2025 onwards** (after linear fit implementation). Calculated during export for both new and existing recordings. If not present, use `clock_offset` instead. See "Clock Offset vs Linear Fit Offset" section above for details.
- **Channel filtering**: The `channel_labels` in `stream_info` now shows **only the channels that were recorded**, not all available channels. The keys ("0", "1", "2", ...) match the `data` array indices directly. Use `filtered_channel_indices` to see which original channel numbers were recorded, and `original_channel_count` to see how many total channels were available in the stream.
- **Session stores channel info**: All channel mapping information is stored in the session/export files. You don't need to check project settings - the `stream_info` contains everything you need.
- **Data vs Raw Data**: For numeric streams they're identical; for markers, `data` is parsed JSON and `raw_data` is the original string.
- **No recording fault**: If you see 6 channels in the data and 6 in channel_labels (but 15 in original_channel_count), this is normal - it means channel filtering was applied during recording. Only the selected channels (0-5 in this example) were recorded. The other 9 channels (motion sensors) are available but were not selected for recording.
- **Clock synchronization**: The `timestamp` field uses simple offset correction (`original_timestamp + clock_offset`). For improved accuracy, especially in longer recordings, consider using `linear_fit_offset` which accounts for clock drift.
- **CSV format**: CSV export is a flattened version of JSON. Multi-channel numeric data (4+ channels) is stored as a JSON string in `data_array` column for easy parsing in analysis tools.