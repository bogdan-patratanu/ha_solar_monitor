# Sensor Monitoring Improvements

## Summary of Enhancements

This document summarizes the three major improvements implemented for the solar monitor system.

---

## 1. ✅ Fixed Temperature Sensor

### Problem
The `inverter_temperature` was reading **0.2°C** instead of the actual **~42°C**.

### Root Cause
- Wrong register address (500 instead of 91)
- Missing offset parameter (1000)
- Wrong data type (uint16 instead of int16)

### Solution
Updated `app/templates/deye/common/inverter.yaml`:
```yaml
inverter_temperature:
  address: 91          # Changed from 500 to 91 (0x5B)
  data_type: int16     # Changed from uint16 to int16 (signed)
  offset: 1000         # Added offset parameter
  factor: 0.1
```

Updated `app/parsers/register_parser.py`:
- Added `offset` field to `RegisterConfig`
- Updated `Int16Parser` to apply offset before scaling
- Formula: `result = (raw_value - offset) * factor`

### Expected Result
Temperature will now read correctly: **41.8°C** ✓

---

## 2. ✅ Added State Lookup Tables

### Problem
Sensors like `inverter_state` showed raw numeric values (e.g., `2.0`) instead of human-readable states.

### Solution
Added lookup table support to the parser system:

**Updated `RegisterConfig`:**
```python
@dataclass
class RegisterConfig:
    lookup: dict = None  # New field for state lookups
```

**Updated `UInt16Parser`:**
```python
# Check for lookup table
if config.lookup:
    lookup_value = config.lookup.get(value, config.lookup.get('default', f"Unknown ({value})"))
    return lookup_value
```

**Updated Template:**
```yaml
inverter_state:
  address: 59          # Fixed from 500
  data_type: uint16
  lookup:
    0: "Standby"
    1: "Self-test"
    2: "Normal"
    3: "Alarm"
    4: "Fault"
    default: "Unknown"
```

### Expected Result
- `inverter_state` will show **"Normal"** instead of `2.0` ✓
- Easy to add more lookup tables for other enum sensors

---

## 3. ✅ Created Sensor Health Dashboard

### Features
New `app/sensor_health.py` module provides:

**Real-time Monitoring:**
- Track success/failure rate per sensor
- Overall system health statistics
- Sensor value type tracking
- Last successful read timestamp

**Health Metrics:**
- **Healthy**: ≥95% success rate ✓
- **Degraded**: 80-95% success rate ⚠
- **Unhealthy**: <80% success rate ✗

**Dashboard Output:**
```
============================================================
SENSOR HEALTH DASHBOARD
============================================================
Total Sensors: 65
Total Reads: 325
Success Rate: 98.5%

Sensor Status:
  ✓ Healthy (≥95%): 63
  ⚠ Degraded (80-95%): 2
  ✗ Unhealthy (<80%): 0

Last Update: 2026-01-02 11:45:30
============================================================
```

**Detailed Reports:**
- Per-sensor statistics
- Problematic sensor identification
- Value type breakdown
- Failure timestamps

### Usage

**Option 1: Use the new monitoring script**
```bash
python app/main_dev_with_health.py
```
Shows health dashboard every 5 reads automatically.

**Option 2: Integrate into existing code**
```python
from sensor_health import SensorHealth

sensor_health = SensorHealth()

# Record sensor readings
for sensor_id, value in data.items():
    sensor_health.record_sensor(sensor_id, value, success=True)

# Display summary
print(sensor_health.get_summary())

# Or detailed report
print(sensor_health.get_detailed_report())
```

---

## Additional Improvements Made

### DateTime Parser
- Fixed inverter datetime decoding
- Now shows: `"2026-01-02 11:28:29"` instead of hex `"1A01 020B 1C1D"`
- Based on ha-solarman reference implementation

### Endianness Fix
- All Deye 32-bit sensors now use `endianness: little`
- Fixed incorrect power and energy readings
- All totals now show correct values

### Data Type Refactoring
- Clean Strategy Pattern implementation
- Explicit `data_type` in all 32 template files
- Support for: uint16, int16, uint32, int32, sum, raw, datetime
- Backward compatible with legacy configs

---

## Files Modified

### Core Parser System
- `app/parsers/register_parser.py` - Added offset, lookup, datetime support
- `app/parsers/__init__.py` - Exported new types

### Templates
- `app/templates/deye/common/inverter.yaml` - Fixed temperature, state, datetime
- All 32 template files - Added `endianness: little` for 32-bit sensors

### New Files
- `app/sensor_health.py` - Health monitoring module
- `app/main_dev_with_health.py` - Monitoring script with dashboard
- `app/test_raw_parser.py` - Parser testing utility

---

## Testing

Run the monitoring script to see all improvements:
```bash
cd app
python main_dev_with_health.py
```

Expected output will show:
- ✅ Correct temperature (~42°C)
- ✅ Human-readable states ("Normal")
- ✅ Proper datetime format
- ✅ Health dashboard every 5 reads
- ✅ All sensor values accurate

---

## Next Steps (Optional)

Future enhancements to consider:
1. Add battery state lookup table
2. Decode alarm/fault bitmasks to readable messages
3. Add data validation rules (min/max ranges)
4. Export health metrics to file/database
5. Add alerting for unhealthy sensors
6. Create web dashboard for real-time monitoring

---

**Implementation Date:** 2026-01-02
**Status:** ✅ Complete and Ready for Testing
