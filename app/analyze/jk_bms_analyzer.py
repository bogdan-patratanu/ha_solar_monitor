#!/usr/bin/env python3
"""
JK BMS Analyzer
Supports both Modbus RTU and JK proprietary protocol
"""
import argparse
import serial
import time
import signal
from pymodbus.client import ModbusSerialClient

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

class timeout_context:
    def __init__(self, seconds):
        self.seconds = seconds
    
    def __enter__(self):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.seconds)
    
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

def check_for_continuous_data(port, baudrate, duration=1.0):
    """Check if port is transmitting continuous data (non-Modbus protocol)"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        time.sleep(0.2)  # Let buffer fill
        waiting = ser.in_waiting
        
        if waiting > 50:  # More than 50 bytes waiting indicates continuous transmission
            data = ser.read(min(100, waiting))
            ser.close()
            print(f"⚠ Detected continuous data stream ({waiting} bytes waiting)")
            print(f"  Sample: {' '.join(f'0x{b:02X}' for b in data[:20])}")
            return True
        
        ser.close()
        return False
        
    except Exception as e:
        print(f"  Error checking for continuous data: {e}")
        return False


def scan_for_devices(port, baudrate):
    """Scan for multiple BMS devices on the bus"""
    print("\n" + "="*80)
    print(f"SCANNING FOR MULTIPLE BMS DEVICES AT {baudrate} BAUD")
    print("="*80 + "\n")
    
    # Check for continuous data first
    if check_for_continuous_data(port, baudrate):
        print("  → Skipping Modbus scan (proprietary protocol detected)")
        print("  → Use --mode proprietary to analyze this protocol\n")
        return []
    
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=0.3,
        retries=0,
        bytesize=8,
        parity='N',
        stopbits=1
    )
    
    try:
        if not client.connect():
            print("❌ Failed to connect via Modbus")
            return []
        
        print(f"✓ Connected to {port}\n")
        print("Scanning device IDs 1-10...")
        
        found_devices = []
        
        for device_id in range(1, 11):
            try:
                with timeout_context(2):  # 2 second timeout per device
                    result = client.read_holding_registers(0, count=1, device_id=device_id)
                    if not result.isError():
                        print(f"  ✓ Device ID {device_id}: FOUND")
                        found_devices.append(device_id)
                    else:
                        print(f"    Device ID {device_id}: No response")
            except TimeoutError:
                print(f"    Device ID {device_id}: Timeout")
            except Exception as e:
                print(f"    Device ID {device_id}: Error ({type(e).__name__})")
        
        print(f"\n{'='*80}")
        print(f"Found {len(found_devices)} device(s): {found_devices}")
        print(f"{'='*80}\n")
        
        return found_devices
        
    finally:
        client.close()


def analyze_jk_modbus(port, baudrate, device_id):
    """Try to read JK BMS via Modbus RTU"""
    print("\n" + "="*80)
    print(f"JK BMS - MODBUS RTU ANALYSIS (Device ID: {device_id})")
    print("="*80 + "\n")
    
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=1.0,
        retries=3,
        bytesize=8,
        parity='N',
        stopbits=1
    )
    
    try:
        if not client.connect():
            print("❌ Failed to connect via Modbus")
            return False
        
        print(f"✓ Connected to {port} at {baudrate} baud (device_id: {device_id})\n")
        
        # Try common JK BMS register ranges
        ranges_to_try = [
            (0, 50, "Device Info (0-49)"),
            (0x1000, 50, "Cell Voltages (0x1000-0x1031)"),
            (0x2000, 20, "BMS Status (0x2000-0x2013)"),
            (100, 50, "Alternative Range (100-149)"),
        ]
        
        found_data = False
        
        for start, count, description in ranges_to_try:
            print(f"Trying {description}...")
            try:
                result = client.read_holding_registers(start, count=count, device_id=device_id)
                if not result.isError():
                    non_zero = [v for v in result.registers if v != 0]
                    if non_zero:
                        print(f"✓ Found {len(non_zero)} non-zero values!")
                        found_data = True
                        
                        # Display the data
                        print(f"\nRegisters {start}-{start+count-1}:")
                        for i, val in enumerate(result.registers[:20]):  # Show first 20
                            if val != 0:
                                signed = val if val < 32768 else val - 65536
                                print(f"  R{start+i:5d}: {val:5d} (0x{val:04x}) signed: {signed:6d}")
                        if len(result.registers) > 20:
                            print(f"  ... and {len(result.registers)-20} more registers")
                        print()
                    else:
                        print("  All zeros")
                else:
                    print(f"  Error: {result}")
            except Exception as e:
                print(f"  Exception: {e}")
        
        return found_data
        
    finally:
        client.close()


def analyze_jk_proprietary(port, baudrate=115200, duration=5):
    """Analyze JK BMS proprietary protocol"""
    print("\n" + "="*80)
    print("JK BMS - PROPRIETARY PROTOCOL ANALYSIS")
    print("="*80 + "\n")
    
    print(f"Listening on {port} at {baudrate} baud for {duration} seconds...\n")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        start_time = time.time()
        all_data = bytearray()
        packet_count = 0
        
        # JK BMS protocol markers
        # Common start bytes: 0x4E, 0x57, 0xAA, 0x55
        # Common patterns: 4E 57 [length] [data] [checksum]
        
        while time.time() - start_time < duration:
            data = ser.read(1024)
            if data:
                all_data.extend(data)
        
        ser.close()
        
        if not all_data:
            print("❌ No data received")
            return False
        
        print(f"✓ Received {len(all_data)} bytes\n")
        
        # Analyze the data
        print("-" * 80)
        print("BYTE FREQUENCY ANALYSIS:")
        print("-" * 80)
        
        byte_freq = {}
        for byte in all_data:
            byte_freq[byte] = byte_freq.get(byte, 0) + 1
        
        # Show top 10 most frequent bytes
        sorted_freq = sorted(byte_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        for byte_val, count in sorted_freq:
            percentage = (count / len(all_data)) * 100
            print(f"  0x{byte_val:02X} ({chr(byte_val) if 32 <= byte_val < 127 else '.'})  : {count:5d} times ({percentage:5.1f}%)")
        
        # Look for packet patterns
        print("\n" + "-" * 80)
        print("PACKET PATTERN DETECTION:")
        print("-" * 80)
        
        # Common JK BMS start sequences
        patterns = [
            (b'\x4E\x57', "JK BMS (0x4E 0x57)"),
            (b'\xAA\x55', "Generic (0xAA 0x55)"),
            (b'\x55\xAA', "Generic (0x55 0xAA)"),
            (b'\xDD\xA5', "JK BMS Alt (0xDD 0xA5)"),
        ]
        
        for pattern, name in patterns:
            count = all_data.count(pattern)
            if count > 0:
                print(f"  {name}: Found {count} times")
                
                # Show first occurrence
                idx = all_data.find(pattern)
                if idx >= 0 and idx + 32 < len(all_data):
                    print(f"    First at byte {idx}:")
                    hex_str = ' '.join(f'{b:02X}' for b in all_data[idx:idx+32])
                    print(f"    {hex_str}")
        
        # Show first 128 bytes as hex dump
        print("\n" + "-" * 80)
        print("FIRST 128 BYTES (HEX DUMP):")
        print("-" * 80)
        
        for i in range(0, min(128, len(all_data)), 16):
            hex_part = ' '.join(f'{b:02X}' for b in all_data[i:i+16])
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in all_data[i:i+16])
            print(f"{i:04X}:  {hex_part:<48}  {ascii_part}")
        
        print("\n" + "="*80 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='JK BMS Analyzer (Modbus + Proprietary Protocol)')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--mode', choices=['modbus', 'proprietary', 'both', 'scan'], default='scan',
                        help='Analysis mode (default: scan)')
    parser.add_argument('--baudrate', type=int, default=115200,
                        help='Baudrate for proprietary protocol (default: 115200)')
    parser.add_argument('--modbus-baudrate', type=int, default=9600,
                        help='Baudrate for Modbus (default: 9600)')
    parser.add_argument('--device-id', type=int, default=None,
                        help='Modbus device ID (default: auto-scan)')
    parser.add_argument('--duration', type=int, default=5,
                        help='Listening duration for proprietary protocol (default: 5 seconds)')
    
    args = parser.parse_args()
    
    if args.mode in ['modbus', 'both', 'scan']:
        print("\n" + "="*80)
        print("ATTEMPTING MODBUS RTU CONNECTION")
        print("="*80)
        
        # Try common baudrates for JK BMS Modbus
        baudrates = [args.modbus_baudrate, 9600, 115200, 19200]
        
        found_devices = []
        working_baudrate = None
        
        for baud in baudrates:
            devices = scan_for_devices(args.port, baud)
            if devices:
                found_devices = devices
                working_baudrate = baud
                break
        
        if found_devices:
            print(f"\n✓ Found {len(found_devices)} BMS device(s) at {working_baudrate} baud")
            print(f"  Device IDs: {found_devices}\n")
            
            # Analyze each device
            for dev_id in found_devices:
                analyze_jk_modbus(args.port, working_baudrate, dev_id)
                print("\n")
        else:
            print("\n⚠ No Modbus devices found")
            
            # If specific device ID provided, try it anyway
            if args.device_id is not None:
                print(f"\nTrying specific device ID {args.device_id}...")
                analyze_jk_modbus(args.port, args.modbus_baudrate, args.device_id)
    
    if args.mode in ['proprietary', 'both']:
        print("\n" + "="*80)
        print("ATTEMPTING PROPRIETARY PROTOCOL DETECTION")
        print("="*80)
        
        # Try common JK BMS baudrates
        baudrates = [args.baudrate, 115200, 9600, 19200]
        
        for baud in baudrates:
            print(f"\nTrying baudrate {baud}...")
            if analyze_jk_proprietary(args.port, baud, args.duration):
                break


if __name__ == "__main__":
    main()
