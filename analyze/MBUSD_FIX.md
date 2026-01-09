# mbusd Configuration Fix for Deye Inverter

## Problem Identified

TCP connection succeeds but mbusd times out waiting for responses from the inverter:
```
No response received after 3 retries, continue with next request
```

## Root Cause

Your mbusd configuration has `wait = 500` (500ms), but the Deye inverter needs more time to respond, especially when reading multiple registers.

## Solution

Update `/etc/mbusd/deye.conf` with these critical changes:

### 1. Increase Response Wait Time

```ini
# Change from:
wait = 500

# To:
wait = 2000
```

### 2. Increase Pause Between Requests

```ini
# Change from:
pause = 100

# To:
pause = 200
```

### 3. Enable Debug Logging (Temporarily)

```ini
# Change from:
loglevel = 2

# To:
loglevel = 3

# Add log file:
logfile = /var/log/mbusd-deye.log
```

## Complete Recommended Configuration

Copy the file `deye.conf.recommended` to `/etc/mbusd/deye.conf`:

```bash
# Backup current config
sudo cp /etc/mbusd/deye.conf /etc/mbusd/deye.conf.backup

# Copy recommended config
sudo cp deye.conf.recommended /etc/mbusd/deye.conf

# Restart mbusd
sudo systemctl restart mbusd@deye.service

# Wait for service to start
sleep 3

# Check status
sudo systemctl status mbusd@deye.service

# Test connection
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 0
```

## Alternative: Manual Edit

Edit `/etc/mbusd/deye.conf`:

```bash
sudo nano /etc/mbusd/deye.conf
```

Change these lines:
- `loglevel = 2` → `loglevel = 3`
- `pause = 100` → `pause = 200`
- `wait = 500` → `wait = 2000`
- Add: `logfile = /var/log/mbusd-deye.log`

Save and restart:
```bash
sudo systemctl restart mbusd@deye.service
```

## Verify Fix

### 1. Check mbusd logs:
```bash
sudo tail -f /var/log/mbusd-deye.log
```

### 2. Run test script:
```bash
python test_mbusd_forwarding.py 192.168.69.3 --port 502 --device-id 0
```

### 3. Run full read:
```bash
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 0
```

## Expected Output After Fix

```
✓ Connected to 192.168.69.3:502 (device_id: 0)

================================================================================
DEYE INVERTER - READING REGISTER ADDRESSES
================================================================================

Reading Device Info & Status (0-99)...
✓ Read 100 registers

Reading Energy Counters (76-100)...
✓ Read 25 registers
...
```

## Why This Works

- **wait = 2000**: Gives inverter 2 seconds to respond (was 500ms)
- **pause = 200**: Adds 200ms delay between requests to prevent overwhelming the inverter
- **loglevel = 3**: Shows detailed communication for debugging

The Deye inverter is slower to respond over Modbus RTU, especially when reading large register blocks. The default 500ms timeout is insufficient.

## Troubleshooting

If still not working after config change:

### Check mbusd is using new config:
```bash
sudo systemctl restart mbusd@deye.service
ps aux | grep mbusd
cat /proc/$(pgrep mbusd)/cmdline | tr '\0' ' '
```

### Verify serial port is accessible:
```bash
ls -l /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
# Should show permissions allowing mbusd user to access
```

### Check for serial port conflicts:
```bash
sudo lsof /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
# Should only show mbusd process
```

### Monitor real-time logs:
```bash
# Terminal 1: Watch logs
sudo tail -f /var/log/mbusd-deye.log

# Terminal 2: Run test
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 0
```

## Performance Tuning

After it works, you can optimize:

1. **Reduce wait time gradually**: Try 1500ms, then 1000ms
2. **Reduce pause time**: Try 150ms, then 100ms
3. **Test with different register counts**: Find optimal block size

```bash
# Test different configurations
python test_mbusd_forwarding.py 192.168.69.3 --test counts --device-id 0
```

## Revert to Production Settings

Once working, reduce logging:

```bash
sudo nano /etc/mbusd/deye.conf
# Change: loglevel = 3 → loglevel = 2
sudo systemctl restart mbusd@deye.service
```
