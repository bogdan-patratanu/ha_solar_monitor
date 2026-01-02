#!/usr/bin/env python3
"""
Capture raw data from JK BMS to analyze the protocol
"""
import serial
import sys
import time
from collections import Counter

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
duration = int(sys.argv[3]) if len(sys.argv) > 3 else 3

print(f"Capturing raw data from {port} at {baudrate} baud for {duration} seconds...")

try:
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1
    )
    
    # Clear buffer
    ser.reset_input_buffer()
    time.sleep(0.5)
    
    start_time = time.time()
    all_data = bytearray()
    
    while time.time() - start_time < duration:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            all_data.extend(data)
    
    ser.close()
    
    print(f"\n✓ Captured {len(all_data)} bytes\n")
    
    if len(all_data) == 0:
        print("❌ No data received!")
        sys.exit(1)
    
    # Byte frequency analysis
    print("="*80)
    print("BYTE FREQUENCY (Top 20):")
    print("="*80)
    counter = Counter(all_data)
    for byte_val, count in counter.most_common(20):
        percentage = (count / len(all_data)) * 100
        ascii_char = chr(byte_val) if 32 <= byte_val < 127 else '.'
        print(f"  0x{byte_val:02X} ({ascii_char:3s}): {count:6d} times ({percentage:5.1f}%)")
    
    # Look for potential frame markers (2-byte sequences that repeat)
    print("\n" + "="*80)
    print("POTENTIAL FRAME MARKERS (2-byte sequences):")
    print("="*80)
    
    two_byte_sequences = {}
    for i in range(len(all_data) - 1):
        seq = bytes([all_data[i], all_data[i+1]])
        if seq not in two_byte_sequences:
            two_byte_sequences[seq] = []
        two_byte_sequences[seq].append(i)
    
    # Find sequences that appear multiple times with regular spacing
    markers = []
    for seq, positions in two_byte_sequences.items():
        if len(positions) >= 3:
            spacings = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
            avg_spacing = sum(spacings) / len(spacings)
            min_spacing = min(spacings)
            max_spacing = max(spacings)
            
            # If spacing is relatively consistent and reasonable (50-500 bytes)
            if 50 < avg_spacing < 500 and (max_spacing - min_spacing) < 50:
                markers.append((seq, len(positions), avg_spacing, min_spacing, max_spacing))
    
    # Sort by frequency
    markers.sort(key=lambda x: x[1], reverse=True)
    
    for seq, count, avg_spacing, min_spacing, max_spacing in markers[:10]:
        print(f"  {seq.hex().upper():6s}: {count:3d} times, avg spacing: {avg_spacing:6.1f} bytes (range: {min_spacing}-{max_spacing})")
    
    # Show first 500 bytes in hex to see more of the pattern
    print("\n" + "="*80)
    print("FIRST 500 BYTES (HEX):")
    print("="*80)
    
    for i in range(0, min(500, len(all_data)), 16):
        hex_str = ' '.join(f'{b:02X}' for b in all_data[i:i+16])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in all_data[i:i+16])
        print(f"{i:04d}:  {hex_str:48s}  {ascii_str}")
    
    # Look for potential response frames (longer sequences)
    print("\n" + "="*80)
    print("LOOKING FOR RESPONSE FRAMES (sequences > 50 bytes):")
    print("="*80)
    
    # Find sequences of non-repeating data
    i = 0
    while i < len(all_data) - 50:
        # Skip the repeating poll pattern
        if all_data[i:i+10] == b'\x0D\x10\x16\x20\x00\x01\x02\x00\x00\x83':
            i += 13
            continue
        
        # Skip idle bytes
        if all_data[i] == 0xE0:
            i += 1
            continue
        
        # Found something different - might be a response
        start = i
        while i < len(all_data) and all_data[i] != 0xE0 and all_data[i:i+10] != b'\x0D\x10\x16\x20\x00\x01\x02\x00\x00\x83':
            i += 1
        
        length = i - start
        if length > 20:  # Potential response frame
            print(f"\nPotential response at byte {start}, length {length}:")
            response = all_data[start:start+min(100, length)]
            for j in range(0, len(response), 16):
                hex_str = ' '.join(f'{b:02X}' for b in response[j:j+16])
                print(f"  {hex_str}")
            if length > 100:
                print(f"  ... ({length - 100} more bytes)")
        
        i = start + 1
    
    # Look for repeating patterns
    print("\n" + "="*80)
    print("REPEATING PATTERNS (4-16 bytes):")
    print("="*80)
    
    for pattern_len in [4, 6, 8, 10, 12, 16]:
        patterns = {}
        for i in range(len(all_data) - pattern_len):
            pattern = bytes(all_data[i:i+pattern_len])
            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append(i)
        
        # Find patterns that repeat
        repeating = [(p, pos) for p, pos in patterns.items() if len(pos) >= 3]
        repeating.sort(key=lambda x: len(x[1]), reverse=True)
        
        if repeating:
            print(f"\n  {pattern_len}-byte patterns:")
            for pattern, positions in repeating[:3]:
                spacings = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_spacing = sum(spacings) / len(spacings) if spacings else 0
                print(f"    {pattern.hex().upper():32s}: {len(positions):3d} times, avg spacing: {avg_spacing:6.1f}")
    
    # Save to file
    filename = f"jk_raw_capture_{int(time.time())}.bin"
    with open(filename, 'wb') as f:
        f.write(all_data)
    print(f"\n✓ Raw data saved to: {filename}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
