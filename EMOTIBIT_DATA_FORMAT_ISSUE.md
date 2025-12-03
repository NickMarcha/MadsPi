# EmotiBit Data Format Investigation

## Problem Statement

Recorded EmotiBit values from BrainFlow do not match expected units when compared to:
1. EmotiBit Oscilloscope readings
2. EmotiBit documentation for SD card recordings
3. Expected sensor ranges

### Observed Values vs Expected

| Sensor | Observed Value | Expected Value | Issue |
|--------|---------------|----------------|-------|
| Temperature (T1) | `50507.0` | ~36°C | Value is ~1400x too high |
| Humidity (H0) | `0.243` | ~100% | Value is ~400x too low |
| EDA (EA) | `-0.239` | ~5 microsiemens | Negative value is unusual |

## Investigation Findings

### 1. EmotiBit Documentation Analysis

**From `external_docs/EmotiBit/Working_with_emotibit_data.md`:**

When EmotiBit records to SD card, the firmware outputs:
- **Temperature (T1)**: Already in degrees Celsius (e.g., `33.037` in raw data examples)
- **EDA (EA)**: Already in microsiemens (e.g., `0.030269` in raw data examples)
- **Humidity (H0)**: Expected in percent (0-100)

**Key Finding**: The documentation shows that EmotiBit firmware converts raw sensor values to meaningful units when recording to SD card.

### 2. BrainFlow Source Code Analysis

**From `external_docs/brainflow/emotibit.cpp`:**

- **Line 366**: Temperature data: `anc_packages[i][temperature_channel] = std::stod(payload[i]);`
- **Line 407**: EDA data: `anc_packages[i][eda_channel] = std::stod(payload[i]);`

**Key Finding**: BrainFlow does **NO data conversion** - it simply parses the raw string values from EmotiBit using `std::stod()` (string to double). This means BrainFlow passes through whatever format EmotiBit sends over the network, which may differ from the format used when recording to SD card.

### 3. BrainFlow Preset Structure

According to BrainFlow C++ source code, EmotiBit uses three separate data presets:

- **DEFAULT_PRESET (0)**: Accelerometer, gyroscope, magnetometer
- **AUXILIARY_PRESET (1)**: PPG (Photoplethysmogram) data
- **ANCILLARY_PRESET (2)**: EDA (Electrodermal Activity) and temperature data

**Current Implementation Issue**: The code currently only reads from DEFAULT_PRESET (default behavior when calling `get_board_data()` without arguments).

### 4. Diagnostic Data from Logs

**From `logs/madspipeline_20251203_153209.log`:**

```
Line 107: DEFAULT_PRESET: Could not read - "INVALID_ARGUMENTS_ERROR:13 invalid num_samples"
Line 108: AUXILIARY_PRESET: shape=(12, 1), first sample: [9019.0, -0.745, 0.21, -0.686, -1.587, -13.977, -3.448, -33.0, -41.0, -57.0, 1764772341.5712547, 0.0]
Line 109: ANCILLARY_PRESET: shape=(12, 2), first sample: [9019.0, -0.751, 0.205, -0.686, 1.312, -8.911, -1.556, -32.0, -43.0, -55.0, 1764772341.5712569, 0.0]
```

**Observations**:
- Both AUXILIARY and ANCILLARY presets show 12 channels with motion sensor data (not the expected PPG/temperature/EDA)
- Channel 0 in both presets shows `9019.0` (could be package number or a sensor value)
- Channels 1-9 show accelerometer, gyroscope, and magnetometer values
- Channel 10 shows timestamp
- Channel 11 shows marker (0.0)

**Mystery**: The diagnostic shows motion sensors in AUXILIARY and ANCILLARY presets, but the user is seeing temperature/EDA/PPG values in their exports. This suggests:
1. `get_board_data()` without arguments may behave differently than when called with a specific preset
2. The channel mapping may be incorrect
3. BrainFlow may combine presets in a way not reflected in the diagnostic

### 5. Board Description Analysis

**From logs**: `get_board_descr()` only describes DEFAULT_PRESET:

```python
{
    'accel_channels': [1, 2, 3],
    'gyro_channels': [4, 5, 6],
    'magnetometer_channels': [7, 8, 9],
    'marker_channel': 11,
    'name': 'Emotibit',
    'num_rows': 12,
    'package_num_channel': 0,
    'sampling_rate': 25,
    'timestamp_channel': 10
}
```

**Key Finding**: `get_board_descr()` is **incomplete** - it only shows DEFAULT_PRESET channels and does not include information about AUXILIARY_PRESET (PPG) or ANCILLARY_PRESET (temperature/EDA) channels.

## Current Implementation

### Code Location
- `src/madspipeline/emotibit_brainflow.py`

### Current Behavior
1. Reads from DEFAULT_PRESET only (default when calling `get_board_data()` without arguments)
2. Maps channels 0-5 as: Temperature, Humidity, EDA, PPG_IR, PPG_Red, PPG_Green
3. Maps channels 6-11 as: Accel_X, Accel_Y, Accel_Z, Gyro_X, Gyro_Y, Gyro_Z

### Issue
The channel mapping assumes temperature/EDA/PPG are in DEFAULT_PRESET, but according to BrainFlow source code, they should be in separate presets.

## Hypotheses

1. **Network Format vs SD Card Format**: EmotiBit may send data in a different format over the network than when recording to SD card. The network format might be raw/unconverted values.

2. **Preset Combination**: BrainFlow may combine all presets into DEFAULT_PRESET when called without arguments, but the channel mapping is incorrect.

3. **Missing Conversion**: The values may need conversion formulas (similar to EDA transform parameters mentioned in EmotiBit docs: `eda_transform_slope` and `eda_transform_intercept`).

4. **Channel Mapping Error**: The current channel mapping (assuming temperature/EDA/PPG in channels 0-5) may be completely wrong, and these values might be in different channels or presets.

## Next Steps

1. **Enhanced Diagnostics**: 
   - Use `get_current_board_data()` instead of `get_board_data()` to read individual presets
   - Log what the main loop receives when calling `get_board_data()` without arguments
   - Identify which channels actually contain data in each preset

2. **Multi-Preset Reading**:
   - If presets are separate, read from all three presets (DEFAULT, AUXILIARY, ANCILLARY)
   - Combine them into a single LSL stream with correct channel mapping
   - Map channels based on actual data location, not assumptions

3. **Data Format Investigation**:
   - Compare network data format with SD card format
   - Check if conversion formulas are needed (e.g., temperature from millidegrees to Celsius)
   - Verify EDA transform parameters apply to network data

4. **Channel Mapping Verification**:
   - Use BrainFlow's channel getter methods if available (e.g., `get_temperature_channels()`, `get_eda_channels()`, `get_ppg_channels()`)
   - Verify actual channel indices for each sensor type
   - Update channel labels based on verified mapping

## References

- `external_docs/EmotiBit/Working_with_emotibit_data.md` - EmotiBit data format documentation
- `external_docs/brainflow/emotibit.cpp` - BrainFlow EmotiBit implementation
- `external_docs/brainflow/dataformatdesc.html` - BrainFlow data format description
- `single dataentry.md` - Current data entry documentation
- `logs/madspipeline_20251203_153209.log` - Diagnostic log output

## Status

**Current Status**: FIXED

**Last Updated**: 2025-12-03

**Solution Implemented**: 
- Modified `emotibit_brainflow.py` to read from all three presets (DEFAULT, AUXILIARY, ANCILLARY)
- Combined data from all presets into a single LSL stream with correct channel mapping:
  - ANCILLARY_PRESET channels 1-3: Humidity, Temperature, EDA
  - AUXILIARY_PRESET channels 1-3: PPG_IR, PPG_Red, PPG_Green
  - DEFAULT_PRESET channels 1-9: Accel (X,Y,Z), Gyro (X,Y,Z), Mag (X,Y,Z)
- Updated channel names and units to match actual data locations
- Temperature values now correctly read from ANCILLARY_PRESET channel 2 (showing ~37°C instead of ~50507)

**Verification**: Test with latest logs shows ANCILLARY_PRESET contains temperature at channel 2 with value 37.573°C (correct range)

