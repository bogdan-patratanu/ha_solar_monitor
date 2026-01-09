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
            
            # Byte frequency
            from collections import Counter
            freq = Counter(buffer)
            print("\nByte frequency (top 10):")
            for byte, count in freq.most_common(10):
                print(f"  {byte:02x}: {count} times")
            
            # Check for common protocol headers
            common_headers = {
                'modbus': b'\x00\x01\x00\x00',  # Modbus TCP header
                'jk_bms': b'\xc1\x41\xf8\x00',  # JK BMS header pattern
                'custom_rtu': b'\xe1\xc0\x01\xf8',  # Custom RTU header pattern
            }
            common_function_codes = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0F, 0x10]  # Common Modbus function codes

            found_protocols = []
            # Check for Modbus TCP and JK BMS by header presence
            for name, header in common_headers.items():
                if header in buffer:
                    found_protocols.append(name)

            # Check for Modbus RTU by scanning for function code in the second byte of any potential message
            found_rtu = False
            for i in range(len(buffer)-1):
                # Check if the next byte is a function code and the current byte is the device address (any byte)
                if buffer[i+1] in common_function_codes:
                    found_rtu = True
                    break
            if found_rtu:
                found_protocols.append('rtu')
            
            if found_protocols:
                print(f"\nDetected protocol headers: {', '.join(found_protocols)}")
            else:
                print("\nNo known protocol headers detected.")
            
            # Validate detected protocols
            validated_protocols = []
            for protocol in found_protocols:
                if protocol == 'rtu':
                    # Basic Modbus RTU validation: minimum 4-byte structure
                    if any(len(buffer) - i >= 4 and \
                           buffer[i+1] in common_function_codes and \
                           (len(buffer) - i == buffer[i+2] + 5 if buffer[i+1] in [0x0F, 0x10] else True) \
                           for i in range(len(buffer)-3)):
                        validated_protocols.append('rtu')
                else:
                    # For other protocols, just trust header detection for now
                    validated_protocols.append(protocol)
            
            if validated_protocols:
                print(f"\nValidated protocol headers: {', '.join(validated_protocols)}")
            else:
                print("\nNo validated protocol headers detected.")
            
            # If we detected the JK BMS or custom RTU header, do frame analysis
            if 'jk_bms' in found_protocols or 'custom_rtu' in found_protocols:
                if 'jk_bms' in found_protocols:
                    header = b'\xc1\x41\xf8\x00'
                else:
                    header = b'\xe1\xc0\x01\xf8'
                header_len = len(header)
                occurrences = []
                start = 0
                while start < len(buffer):
                    pos = buffer.find(header, start)
                    if pos == -1:
                        break
                    occurrences.append(pos)
                    start = pos + header_len
                
                # If we found at least two occurrences, we can compute the gaps
                if len(occurrences) > 1:
                    gaps = []
                    for i in range(1, len(occurrences)):
                        gap = occurrences[i] - occurrences[i-1]
                        gaps.append(gap)
                    
                    gap_counter = Counter(gaps)
                    if gap_counter:  # might be empty if no gaps
                        common_gap, count_common = gap_counter.most_common(1)[0]
                        print(f"\nFrame analysis:")
                        print(f"  Found {len(occurrences)} frames")
                        print(f"  Most common frame length: {common_gap} bytes (appears {count_common} times)")
                    else:
                        print("\nFrame analysis: Not enough frames to compute gaps")
                else:
                    print("\nFrame analysis: Only one frame found")
            
            # Improved pattern detection with sliding window (for patterns of length 2 to 6)
            pattern_lengths = [2, 3, 4, 5, 6]
            for pat_len in pattern_lengths:
                if len(buffer) < pat_len:
                    continue
                pattern = buffer[:pat_len]
                count = 1
                # Count non-overlapping occurrences
                idx = pat_len
                while idx <= len(buffer) - pat_len:
                    if buffer[idx:idx+pat_len] == pattern:
                        count += 1
                        idx += pat_len
                    else:
                        idx += 1
                if count > 3:  # Arbitrary threshold
                    hex_pattern = ' '.join(f'{b:02x}' for b in pattern)
                    print(f"\nRepeating {pat_len}-byte pattern detected: {hex_pattern} (appears {count} times)")
            
            # Look for repeating sequences
            if len(buffer) >= 3:
                pattern_3 = buffer[:3]
                count_3 = sum(1 for i in range(0, len(buffer) - 2, 3) if buffer[i:i+3] == pattern_3)
                if count_3 > 5:
                    print(f"\nRepeating 3-byte pattern detected: {' '.join(f'{b:02x}' for b in pattern_3)}")
                    print(f"  Appears {count_3} times")
            
            # Frame structure analysis for dominant patterns
            dominant_pattern = None
            dominant_count = 0
            if not validated_protocols and pattern_lengths:
                for pat_len in pattern_lengths:
                    pattern = buffer[:pat_len]
                    count = 1
                    idx = pat_len
                    while idx <= len(buffer) - pat_len:
                        if buffer[idx:idx+pat_len] == pattern:
                            count += 1
                            idx += pat_len
                        else:
                            idx += 1
                    if count > dominant_count and count > 3:
                        dominant_count = count
                        dominant_pattern = pattern
            
            if dominant_pattern:
                hex_pattern = ' '.join(f'{b:02x}' for b in dominant_pattern)
                print(f"\nDominant repeating pattern: {hex_pattern} ({dominant_count} times, {dominant_count*len(dominant_pattern)} bytes)")
                print(f"  Pattern represents {dominant_count*len(dominant_pattern)/len(buffer)*100:.1f}% of total data")
                
                # Custom decoder for 4-byte pattern
                if len(dominant_pattern) == 4:
                    print("\nCustom protocol decoder:")
                    
                    # Extract sample frames
                    frames = [buffer[i:i+4] for i in range(0, len(buffer), 4) \
                             if buffer[i:i+4] == dominant_pattern][:10]
                    
                    for i, frame in enumerate(frames):
                        print(f"  Frame {i+1}:")
                        print(f"    Byte 1: Device ID: {frame[0]:02x}")
                        print(f"    Byte 2: Command: {frame[1]:02x}")
                        print(f"    Byte 3: Parameter: {frame[2]:02x}")
                        print(f"    Byte 4: Checksum: {frame[3]:02x}")
                        
                        # Simple checksum validation (sum of first 3 bytes modulo 256)
                        calc_checksum = (frame[0] + frame[1] + frame[2]) & 0xFF
                        if calc_checksum == frame[3]:
                            print(f"    Checksum valid")
                        else:
                            print(f"    Checksum invalid (calculated: {calc_checksum:02x})")
                
                # Frame decoding for dominant patterns
                frame_length = len(dominant_pattern)
                frames = [buffer[i:i+frame_length] for i in range(0, len(buffer), frame_length) \
                         if buffer[i:i+frame_length] == dominant_pattern]
                
                if frames:
                    print(f"\nFrame analysis for dominant pattern ({len(frames)} frames):")
                    # Decode first 3 frames as example
                    for i, frame in enumerate(frames[:3]):
                        print(f"  Frame {i+1}: {' '.join(f'{b:02x}' for b in frame)}")
        
            # JK BMS protocol validation
            jk_header = b'\xc1\x41\xf8\x00'
            jk_occurrences = []
            start = 0
            while start < len(buffer):
                pos = buffer.find(jk_header, start)
                if pos == -1:
                    break
                jk_occurrences.append(pos)
                start = pos + len(jk_header)
            
            if jk_occurrences:
                print(f"\nJK BMS header found {len(jk_occurrences)} times")
                if len(jk_occurrences) > 1:
                    gaps = [jk_occurrences[i] - jk_occurrences[i-1] for i in range(1, len(jk_occurrences))]
                    gap_counter = Counter(gaps)
                    common_gap, count_common = gap_counter.most_common(1)[0]
                    print(f"  Most common frame length: {common_gap} bytes (appears {count_common} times)")
            else:
                print("\nJK BMS header not detected in data")
            
            # Frame decoding for dominant patterns
            if dominant_pattern:
                frame_length = len(dominant_pattern)
                frames = [buffer[i:i+frame_length] for i in range(0, len(buffer), frame_length) \
                         if buffer[i:i+frame_length] == dominant_pattern]
                
                if frames:
                    print(f"\nFrame analysis for dominant pattern ({len(frames)} frames):")
                    # Decode first 3 frames as example
                    for i, frame in enumerate(frames[:3]):
                        print(f"  Frame {i+1}: {' '.join(f'{b:02x}' for b in frame)}")
                        print(f"    Header: {frame[0]:02x}{frame[1]:02x}{frame[2]:02x}{frame[3]:02x}{frame[4]:02x}{frame[5]:02x}")
                        print(f"    Payload: {frame[6:12].hex(' ')}  CRC: {frame[12]:02x}{frame[13]:02x}")
            
            # JK BMS validation and frame decoding
            if 'jk_bms' in found_protocols:
                jk_frames = []
                for occurrence in jk_occurrences:
                    frame = buffer[occurrence:occurrence+14]
                    jk_frames.append(frame)
                
                if jk_frames:
                    print(f"\nJK BMS frame analysis ({len(jk_frames)} frames):")
                    for i, frame in enumerate(jk_frames[:3]):
                        print(f"  Frame {i+1}: {' '.join(f'{b:02x}' for b in frame)}")
                        print(f"    Header: {frame[0]:02x}{frame[1]:02x}{frame[2]:02x}{frame[3]:02x}")
                        print(f"    Payload: {frame[4:12].hex(' ')}")
                        print(f"    CRC: {frame[12]:02x}{frame[13]:02x}")
            
            # Modbus CRC validation
            if 'rtu' in validated_protocols:
                def modbus_crc(data):
                    crc = 0xFFFF
                    for b in data:
                        crc ^= b
                        for _ in range(8):
                            if crc & 0x0001:
                                crc >>= 1
                                crc ^= 0xA001
                            else:
                                crc >>= 1
                    return crc
                
                valid_frames = 0
                for i in range(len(buffer)-3):
                    if buffer[i+1] in common_function_codes:
                        # Estimate frame length
                        if buffer[i+1] in [0x0F, 0x10]:
                            frame_len = buffer[i+2] + 5
                        else:
                            frame_len = 6  # Minimum frame length
                        
                        if i + frame_len <= len(buffer):
                            frame = buffer[i:i+frame_len]
                            calculated_crc = modbus_crc(frame[:-2])
                            received_crc = frame[-2] << 8 | frame[-1]
                            if calculated_crc == received_crc:
                                valid_frames += 1
                
                print(f"  Valid Modbus frames: {valid_frames}")
                
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
