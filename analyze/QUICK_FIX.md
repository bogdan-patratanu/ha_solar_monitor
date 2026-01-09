# Quick Fix for mbusd Connection Issue

## TL;DR - Most Likely Fix

Your command is using **device_id=0** but Deye inverters use **device_id=1**.

### Try this command:
```bash
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 1
```

**Note:** The script has been updated to use `device_id=1` by default now.

---

## Diagnostic Commands (in order of priority)

### 1. Run the diagnostic script to scan for device IDs:
```bash
cd /path/to/ha_solar_monitor/app/analyze
python debug_mbusd.py 192.168.69.3 --port 502 --scan
```

### 2. Test specific device ID:
```bash
python debug_mbusd.py 192.168.69.3 --port 502 --device-id 1
```

### 3. Compare RTU vs TCP:
```bash
python debug_mbusd.py 192.168.69.3 --port 502 --device-id 1 \
    --compare /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
```

---

## If Still Not Working

### Check mbusd status:
```bash
systemctl status mbusd
journalctl -u mbusd -n 50
```

### Verify port is listening:
```bash
netstat -tlnp | grep 502
```

### Test TCP connection:
```bash
nc -zv 192.168.69.3 502
```

### Restart mbusd:
```bash
systemctl restart mbusd
sleep 3
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 1
```

---

## Common Issues Checklist

- [ ] Using device_id=1 (not 0)
- [ ] mbusd service is running
- [ ] No other process using serial port
- [ ] Port 502 is open and listening
- [ ] mbusd configured with correct serial port path
- [ ] Serial port permissions correct

---

## Expected Output (Working)

```
Attempting TCP connection to 192.168.69.3:502 with device_id=1
Connecting...
✓ Connected to 192.168.69.3:502 (device_id=1)

================================================================================
DEYE INVERTER - READING REGISTER ADDRESSES
================================================================================

Reading Device Info & Status (0-99)...
✓ Read 100 registers
...
```

---

## See Full Documentation

For detailed troubleshooting: `MBUSD_TROUBLESHOOTING.md`
