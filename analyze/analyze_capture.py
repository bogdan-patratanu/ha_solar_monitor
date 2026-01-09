#!/usr/bin/env python3
"""
Analyze the captured JK BMS binary data
"""
import sys

filename = sys.argv[1] if len(sys.argv) > 1 else "analyze/jk_raw_capture_1766907007.bin"

with open(filename, 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes\n")

# Show first 500 bytes
print("="*80)
print("FIRST 500 BYTES (HEX):")
print("="*80)
for i in range(0, min(500, len(data)), 16):
    hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
    print(f"{i:04d}:  {hex_str:48s}  {ascii_str}")

# Look for response frames (non-repeating sequences)
print("\n" + "="*80)
print("LOOKING FOR RESPONSE FRAMES:")
print("="*80)

poll_pattern = b'\x0D\x10\x16\x20\x00\x01\x02\x00\x00\x83'

i = 0
frame_count = 0
while i < len(data) - 50:
    # Skip the repeating poll pattern
    if data[i:i+10] == poll_pattern:
        i += 13
        continue
    
    # Skip idle bytes
    if data[i] == 0xE0:
        i += 1
        continue
    
    # Found something different - might be a response
    start = i
    while i < len(data) and data[i] != 0xE0 and data[i:i+10] != poll_pattern:
        i += 1
    
    length = i - start
    if length > 20:  # Potential response frame
        frame_count += 1
        print(f"\nFrame #{frame_count} at byte {start}, length {length}:")
        response = data[start:start+min(200, length)]
        for j in range(0, len(response), 16):
            hex_str = ' '.join(f'{b:02X}' for b in response[j:j+16])
            print(f"  {j:04d}: {hex_str}")
        if length > 200:
            print(f"  ... ({length - 200} more bytes)")
    
    i = start + 1

print(f"\n✓ Found {frame_count} potential response frames")
