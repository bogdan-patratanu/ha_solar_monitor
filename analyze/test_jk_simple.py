#!/usr/bin/env python3
"""
Simple JK BMS test - try different approaches
"""
import sys
from pymodbus.client import ModbusTcpClient

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.69.3"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 503
device_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1

print(f"Connecting to {host}:{port} device_id={device_id}")

client = ModbusTcpClient(host=host, port=port, timeout=3)

if not client.connect():
    print("Failed to connect")
    sys.exit(1)

print("Connected!\n")

# Try different register addresses and function codes
tests = [
    ("Read Holding 0x1620 (5664)", lambda: client.read_holding_registers(address=0x1620, count=10, device_id=device_id)),
    ("Read Input 0x1620 (5664)", lambda: client.read_input_registers(address=0x1620, count=10, device_id=device_id)),
    ("Read Holding 0x0000", lambda: client.read_holding_registers(address=0x0000, count=10, device_id=device_id)),
    ("Read Holding 0x0001", lambda: client.read_holding_registers(address=0x0001, count=10, device_id=device_id)),
    ("Read Holding 0x1000", lambda: client.read_holding_registers(address=0x1000, count=10, device_id=device_id)),
    ("Read Holding 0x2000", lambda: client.read_holding_registers(address=0x2000, count=10, device_id=device_id)),
]

for name, test_func in tests:
    print(f"Testing: {name}")
    try:
        result = test_func()
        if result.isError():
            print(f"  ❌ Error: {result}")
        else:
            print(f"  ✓ Success! Got {len(result.registers)} registers")
            print(f"    First 10 values: {result.registers[:10]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")
    print()

client.close()
