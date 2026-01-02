#!/usr/bin/env python3
"""
Scan for JK BMS devices and test communication
"""
import sys
from pymodbus.client import ModbusTcpClient

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.69.3"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 503

print(f"Scanning {host}:{port} for JK BMS devices\n")

client = ModbusTcpClient(host=host, port=port, timeout=1)

if not client.connect():
    print("Failed to connect")
    sys.exit(1)

print("Connected to mbusd gateway\n")
print("="*80)

# Scan device IDs 1-15
for device_id in range(1, 16):
    print(f"\nTesting Device ID {device_id}:")
    
    # Try a simple read of register 0
    try:
        result = client.read_holding_registers(address=0, count=1, device_id=device_id)
        if not result.isError():
            print(f"  ✓ Device ID {device_id} RESPONDS!")
            print(f"    Register 0 value: {result.registers[0]}")
            
            # Try reading more registers
            result = client.read_holding_registers(address=0, count=10, device_id=device_id)
            if not result.isError():
                print(f"    First 10 registers: {result.registers}")
            
            # Try the JK BMS specific registers
            for reg_addr, reg_name in [(0x1620, "Live"), (0x161E, "Setup"), (0x161C, "Static")]:
                result = client.read_holding_registers(address=reg_addr, count=5, device_id=device_id)
                if not result.isError():
                    print(f"    ✓ {reg_name} register (0x{reg_addr:04X}): {result.registers[:5]}")
        else:
            print(f"  No response (error: {result})")
    except Exception as e:
        print(f"  Exception: {e}")

print("\n" + "="*80)
print("\nScan complete!")

client.close()
