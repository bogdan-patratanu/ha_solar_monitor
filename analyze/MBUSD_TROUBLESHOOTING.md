# mbusd Troubleshooting Guide for Deye Inverter

## Problem
Direct USB connection works, but TCP connection through mbusd returns no response.

## Most Common Issues

### 1. **Wrong Device ID (MOST LIKELY)**
- **Issue**: Deye inverters typically use `device_id=1`, not `0`
- **Your command uses**: `--device-id 0` (default)
- **Fix**: Try `--device-id 1`

```bash
# Try this instead:
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 1
```

### 2. **mbusd Configuration Issues**

#### Check mbusd is running:
```bash
systemctl status mbusd
# or
ps aux | grep mbusd
```

#### Typical mbusd configuration (`/etc/mbusd/mbusd.conf`):
```ini
device = /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
speed = 9600
mode = 8N1
trx_control = addc
trx_timeout = 60
address = 0.0.0.0
port = 502
maxconn = 32
retries = 3
pause = 100
wait = 35
```

**Key parameters to check:**
- `device`: Must match your USB serial port
- `speed`: Must match inverter baudrate (usually 9600)
- `mode`: Usually `8N1` (8 data bits, No parity, 1 stop bit)
- `port`: Must match your connection port (502)

### 3. **Serial Port Access Conflict**
- **Issue**: Both direct script and mbusd trying to access the same port
- **Check**: Make sure you're not running the direct USB script while mbusd is running
- **Fix**: Stop any direct serial connections before starting mbusd

```bash
# Stop any processes using the serial port
lsof /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
```

### 4. **Firewall Blocking TCP Port 502**
```bash
# Check if port 502 is listening
netstat -tlnp | grep 502

# Check firewall rules (if using iptables)
iptables -L -n | grep 502

# Or for firewalld
firewall-cmd --list-ports
```

### 5. **Timeout Too Short**
- Default timeout in your script: 3 seconds
- mbusd adds latency over serial connection
- **Fix**: Try increasing timeout to 5-10 seconds

### 6. **Wrong Modbus Function Code**
- Some devices require specific function codes
- Your script uses function code 03 (read holding registers)
- Deye inverters typically support this, but verify

## Diagnostic Steps

### Step 1: Run the diagnostic script
```bash
# Scan for responsive device IDs
python debug_mbusd.py 192.168.69.3 --port 502 --scan

# Test specific device ID
python debug_mbusd.py 192.168.69.3 --port 502 --device-id 1

# Compare RTU vs TCP
python debug_mbusd.py 192.168.69.3 --port 502 --device-id 1 \
    --compare /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0
```

### Step 2: Test with netcat
```bash
# Check if mbusd is accepting connections
nc -zv 192.168.69.3 502
```

### Step 3: Monitor mbusd logs
```bash
# Check system logs
journalctl -u mbusd -f

# Or check mbusd log file if configured
tail -f /var/log/mbusd.log
```

### Step 4: Test with modpoll (if available)
```bash
# Test reading register 79 with device ID 1
modpoll -m tcp -a 1 -r 79 -c 1 192.168.69.3
```

## Quick Fixes to Try

### Fix 1: Change device ID to 1
```bash
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 1
```

### Fix 2: Increase timeout
Edit `read_deye_correct.py` line 151:
```python
# Change from:
client = ModbusTcpClient(host=host, port=port, timeout=3, retries=3)

# To:
client = ModbusTcpClient(host=host, port=port, timeout=10, retries=5)
```

### Fix 3: Restart mbusd
```bash
systemctl restart mbusd
# Wait a few seconds
sleep 3
# Try your script again
python read_deye_correct.py 192.168.69.3 --port 502 --mode tcp --device-id 1
```

### Fix 4: Check mbusd is using correct serial port
```bash
# Stop mbusd
systemctl stop mbusd

# Test serial port directly
python read_deye_correct.py /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0

# If that works, restart mbusd
systemctl start mbusd
```

## Expected Behavior

### Working RTU Connection:
```
✓ Connected to /dev/serial/by-path/pci-0000:00:10.0-usb-0:3:1.0-port0 at 9600 baud (device_id: 0)

Reading Device Info & Status (0-99)...
✓ Read 100 registers
...
```

### Working TCP Connection (through mbusd):
```
✓ Connected to 192.168.69.3:502 (device_id: 1)

Reading Device Info & Status (0-99)...
✓ Read 100 registers
...
```

## Common Error Messages

### "Failed to connect"
- mbusd not running
- Wrong IP/port
- Firewall blocking

### "Modbus Error: [Input/Output] Modbus Error"
- Wrong device ID (try 1 instead of 0)
- Serial port not accessible by mbusd
- Wrong serial parameters

### "Timeout waiting for response"
- Device ID mismatch
- mbusd not forwarding to serial port
- Serial port locked by another process

## Verification Checklist

- [ ] mbusd service is running
- [ ] mbusd is configured with correct serial port
- [ ] Serial port permissions are correct (mbusd user can access it)
- [ ] No other process is using the serial port
- [ ] Port 502 is open and listening
- [ ] Using device_id=1 (not 0)
- [ ] Timeout is sufficient (5-10 seconds)
- [ ] Can ping 192.168.69.3
- [ ] Direct USB connection works (to verify inverter is responding)

## Next Steps

1. Run the diagnostic script to identify the issue
2. Check mbusd logs for errors
3. Verify device ID (most likely culprit)
4. Adjust timeout if needed
5. Restart mbusd service
