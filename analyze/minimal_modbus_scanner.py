#!/usr/bin/env python3
"""
MinimalModbus-based Modbus RTU device scanner
"""
import argparse
import minimalmodbus
import serial
import time

def scan_modbus_devices(port: str, baudrate: int, timeout: float = 0.2, start_addr: int = 1, end_addr: int = 247):
    """Scan for Modbus RTU devices using MinimalModbus"""
    print(f"Scanning Modbus RTU devices on {port} at {baudrate} baud")
    print(f"Address range: {start_addr}-{end_addr}")
    print("-" * 60)
    
    active_devices = []
    
    for slave_id in range(start_addr, end_addr + 1):
        try:
            # Create instrument
            instrument = minimalmodbus.Instrument(port, slave_id)
            instrument.serial.baudrate = baudrate
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.bytesize = 8
            instrument.serial.timeout = timeout
            
            # Try reading register 0
            value = instrument.read_register(0, 0)
            print(f"Device found at address {slave_id} (Value: {value})")
            active_devices.append(slave_id)
            
        except Exception as e:
            # Ignore timeouts and other errors
            pass
        
        # Small delay between probes
        time.sleep(0.05)
    
    print("-" * 60)
    print(f"Found {len(active_devices)} active devices: {active_devices}")
    return active_devices


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MinimalModbus RTU Device Scanner')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate (default: 9600)')
    parser.add_argument('--start', type=int, default=1, help='Starting address (default: 1)')
    parser.add_argument('--end', type=int, default=247, help='Ending address (default: 247)')
    args = parser.parse_args()
    
    scan_modbus_devices(args.port, args.baudrate, start_addr=args.start, end_addr=args.end)
