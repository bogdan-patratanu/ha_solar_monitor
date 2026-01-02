#!/usr/bin/env python3
"""
JK BMS Protocol Decoder
Decodes the proprietary protocol found on ttyUSB0
Pattern: 02 10 16 20 00 01 02 00 00 C2 (repeating)
"""
import argparse
import serial
import time
import struct

def decode_jk_protocol(data):
    """Decode JK BMS proprietary protocol"""
    
    print("\n" + "="*80)
    print("JK BMS PROTOCOL DECODER")
    print("="*80 + "\n")
    
    # Look for the repeating pattern
    pattern = bytes([0x02, 0x10, 0x16, 0x20, 0x00, 0x01, 0x02, 0x00, 0x00, 0xC2])
    
    # Find all occurrences
    positions = []
    pos = 0
    while True:
        pos = data.find(pattern, pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 1
    
    print(f"Found {len(positions)} occurrences of pattern: 02 10 16 20 00 01 02 00 00 C2")
    
    if len(positions) > 1:
        distances = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
        if distances:
            avg_distance = sum(distances) / len(distances)
            print(f"Average distance between patterns: {avg_distance:.1f} bytes")
            print(f"Distance range: {min(distances)} - {max(distances)} bytes\n")
    
    # Analyze the structure
    print("-" * 80)
    print("PATTERN ANALYSIS:")
    print("-" * 80)
    
    # The pattern appears to be a frame marker
    # Let's look at what comes before and after
    
    if positions:
        print("\nFirst few occurrences with context:\n")
        for i, pos in enumerate(positions[:5]):
            start = max(0, pos - 10)
            end = min(len(data), pos + 20)
            
            hex_before = ' '.join(f'{b:02X}' for b in data[start:pos])
            hex_pattern = ' '.join(f'{b:02X}' for b in data[pos:pos+10])
            hex_after = ' '.join(f'{b:02X}' for b in data[pos+10:end])
            
            print(f"Occurrence {i+1} at byte {pos}:")
            print(f"  Before:  {hex_before}")
            print(f"  Pattern: [{hex_pattern}]")
            print(f"  After:   {hex_after}")
            print()
    
    # Try to find frame boundaries
    print("-" * 80)
    print("FRAME STRUCTURE ANALYSIS:")
    print("-" * 80)
    
    # Look for potential frame sizes
    if len(positions) >= 2:
        frame_size = positions[1] - positions[0]
        print(f"\nAssumed frame size: {frame_size} bytes")
        
        # Extract and analyze frames
        frames = []
        for i in range(min(10, len(positions)-1)):
            frame_start = positions[i]
            frame_end = positions[i+1]
            frame = data[frame_start:frame_end]
            frames.append(frame)
        
        if frames:
            print(f"Extracted {len(frames)} frames\n")
            
            # Show first few frames
            for i, frame in enumerate(frames[:3]):
                print(f"Frame {i+1} ({len(frame)} bytes):")
                hex_str = ' '.join(f'{b:02X}' for b in frame)
                print(f"  {hex_str}")
                
                # Try to interpret as values
                if len(frame) >= 13:
                    print(f"  Byte interpretation:")
                    print(f"    [0-1]:   0x{frame[0]:02X}{frame[1]:02X} = {struct.unpack('>H', frame[0:2])[0]}")
                    if len(frame) > 2:
                        print(f"    [2]:     0x{frame[2]:02X} = {frame[2]}")
                    if len(frame) > 3:
                        print(f"    [3]:     0x{frame[3]:02X} = {frame[3]}")
                    if len(frame) > 4:
                        print(f"    [4-5]:   0x{frame[4]:02X}{frame[5]:02X} = {struct.unpack('>H', frame[4:6])[0] if len(frame) > 5 else frame[4]}")
                print()
            
            # Check if frames are identical or varying
            unique_frames = set(frames)
            if len(unique_frames) == 1:
                print("⚠ All frames are IDENTICAL - this might be idle/heartbeat data")
            else:
                print(f"✓ Found {len(unique_frames)} unique frame patterns")
                print("  → Data is changing, likely contains sensor readings")
    
    # Look for other patterns
    print("\n" + "-" * 80)
    print("SEARCHING FOR ALTERNATIVE PATTERNS:")
    print("-" * 80)
    
    # Common BMS protocol markers
    markers = [
        (b'\x4E\x57', "JK BMS Standard (0x4E 0x57)"),
        (b'\xDD\xA5', "JK BMS Alt (0xDD 0xA5)"),
        (b'\x55\xAA\xEB\x90', "JK BMS Protocol v2"),
        (b'\x01\x03', "Modbus Read Holding"),
        (b'\x01\x04', "Modbus Read Input"),
    ]
    
    for marker, name in markers:
        count = data.count(marker)
        if count > 0:
            print(f"  {name}: Found {count} times")
    
    print("\n" + "="*80 + "\n")


def capture_and_decode(port, baudrate=115200, duration=5):
    """Capture data and decode"""
    print(f"Capturing data from {port} at {baudrate} baud for {duration} seconds...")
    
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
        
        while time.time() - start_time < duration:
            data = ser.read(1024)
            if data:
                all_data.extend(data)
        
        ser.close()
        
        print(f"✓ Captured {len(all_data)} bytes\n")
        
        if all_data:
            decode_jk_protocol(all_data)
        else:
            print("❌ No data received")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='JK BMS Protocol Decoder')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--duration', type=int, default=5, help='Capture duration in seconds (default: 5)')
    
    args = parser.parse_args()
    
    capture_and_decode(args.port, args.baudrate, args.duration)
