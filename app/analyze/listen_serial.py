#!/usr/bin/env python3
"""
Simple serial port listener to capture raw data from devices
"""
import argparse
import serial
import time
import sys
from datetime import datetime


def listen_serial(port: str, baudrate: int, duration: int = 10, output_format: str = 'hex'):
    """Listen to serial port and display received data"""
    print(f"Opening {port} at {baudrate} baud...")
    print(f"Listening for {duration} seconds...")
    print(f"Output format: {output_format}")
    print("-" * 80)
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=0.1
        )
        
        start_time = time.time()
        byte_count = 0
        buffer = bytearray()
        
        while time.time() - start_time < duration:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                byte_count += len(data)
                buffer.extend(data)
                
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                
                if output_format == 'hex':
                    hex_str = ' '.join(f'{b:02x}' for b in data)
                    print(f"[{timestamp}] ({len(data):3d} bytes) {hex_str}")
                elif output_format == 'ascii':
                    ascii_str = ''.join(chr(b) if 32 <= b < 127 else f'<{b:02x}>' for b in data)
                    print(f"[{timestamp}] ({len(data):3d} bytes) {ascii_str}")
                elif output_format == 'both':
                    hex_str = ' '.join(f'{b:02x}' for b in data)
                    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
                    print(f"[{timestamp}] ({len(data):3d} bytes)")
                    print(f"  HEX:   {hex_str}")
                    print(f"  ASCII: {ascii_str}")
            else:
                time.sleep(0.01)
        
        ser.close()
        
        print("-" * 80)
        print(f"Total bytes received: {byte_count}")
        print(f"Bytes per second: {byte_count / duration:.1f}")
        
        # Analyze patterns
        if buffer:
            print("\nPattern analysis:")
            print(f"First 50 bytes (hex): {' '.join(f'{b:02x}' for b in buffer[:50])}")
            print(f"Last 50 bytes (hex):  {' '.join(f'{b:02x}' for b in buffer[-50:])}")
            
            # Look for repeating sequences
            if len(buffer) >= 3:
                pattern_3 = buffer[:3]
                count_3 = sum(1 for i in range(0, len(buffer) - 2, 3) if buffer[i:i+3] == pattern_3)
                if count_3 > 5:
                    print(f"\nRepeating 3-byte pattern detected: {' '.join(f'{b:02x}' for b in pattern_3)}")
                    print(f"  Appears {count_3} times")
            
    except serial.SerialException as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 0
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Serial Port Listener')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0 or COM3)')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baudrate (default: 9600)')
    parser.add_argument('--duration', type=int, default=10, help='Listen duration in seconds (default: 10)')
    parser.add_argument('--format', choices=['hex', 'ascii', 'both'], default='hex', 
                        help='Output format (default: hex)')
    args = parser.parse_args()
    
    sys.exit(listen_serial(args.port, args.baudrate, args.duration, args.format))
