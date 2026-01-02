#!/usr/bin/env python3
"""
JK BMS Stream Analyzer
Analyzes continuous data stream to find frame boundaries and structure
"""
import argparse
import serial
import time
from collections import Counter

def find_repeating_sequences(data, min_length=4, max_length=20):
    """Find repeating byte sequences that could be frame markers"""
    sequences = {}
    
    for length in range(min_length, max_length + 1):
        for i in range(len(data) - length):
            seq = bytes(data[i:i+length])
            if seq not in sequences:
                sequences[seq] = []
            sequences[seq].append(i)
    
    # Filter to sequences that appear multiple times
    repeating = {seq: positions for seq, positions in sequences.items() if len(positions) >= 3}
    
    # Sort by frequency
    sorted_seqs = sorted(repeating.items(), key=lambda x: len(x[1]), reverse=True)
    
    return sorted_seqs[:20]  # Top 20


def analyze_stream_structure(data):
    """Analyze the structure of the data stream"""
    
    print("\n" + "="*80)
    print("JK BMS STREAM STRUCTURE ANALYSIS")
    print("="*80 + "\n")
    
    print(f"Total bytes captured: {len(data)}")
    print(f"Capture rate: ~{len(data)/3:.0f} bytes/second at 115200 baud\n")
    
    # Byte frequency
    print("-" * 80)
    print("BYTE FREQUENCY (Top 15):")
    print("-" * 80)
    
    counter = Counter(data)
    for byte_val, count in counter.most_common(15):
        percentage = (count / len(data)) * 100
        ascii_char = chr(byte_val) if 32 <= byte_val < 127 else '.'
        print(f"  0x{byte_val:02X} ({ascii_char})  : {count:6d} times ({percentage:5.1f}%)")
    
    # Look for repeating sequences
    print("\n" + "-" * 80)
    print("REPEATING SEQUENCES (potential frame markers):")
    print("-" * 80)
    
    repeating = find_repeating_sequences(data, min_length=3, max_length=12)
    
    if repeating:
        for seq, positions in repeating[:10]:
            if len(positions) >= 5:  # Only show if appears at least 5 times
                hex_seq = ' '.join(f'{b:02X}' for b in seq)
                
                # Calculate spacing between occurrences
                spacings = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_spacing = sum(spacings) / len(spacings) if spacings else 0
                min_spacing = min(spacings) if spacings else 0
                max_spacing = max(spacings) if spacings else 0
                
                print(f"\n  Pattern: {hex_seq}")
                print(f"    Occurrences: {len(positions)}")
                print(f"    Avg spacing: {avg_spacing:.1f} bytes")
                print(f"    Spacing range: {min_spacing} - {max_spacing} bytes")
                
                # Check if spacing is consistent (potential frame marker)
                if spacings and max_spacing - min_spacing < 5:
                    print(f"    → CONSISTENT spacing - likely frame marker!")
    else:
        print("  No repeating sequences found")
    
    # Sample the data at different points
    print("\n" + "-" * 80)
    print("DATA SAMPLES (from different time points):")
    print("-" * 80)
    
    sample_points = [0, len(data)//4, len(data)//2, 3*len(data)//4, len(data)-64]
    
    for i, pos in enumerate(sample_points):
        if pos >= 0 and pos + 64 <= len(data):
            sample = data[pos:pos+64]
            hex_str = ' '.join(f'{b:02X}' for b in sample[:32])
            print(f"\nSample {i+1} (byte {pos}):")
            print(f"  {hex_str}")
            
            # Check for patterns
            if sample[0:3] == sample[13:16]:
                print(f"  → Repeating pattern detected within sample!")
    
    # Look for potential frame sizes
    print("\n" + "-" * 80)
    print("FRAME SIZE ANALYSIS:")
    print("-" * 80)
    
    # Common frame sizes to check
    frame_sizes = [13, 16, 20, 24, 32, 64, 128, 256]
    
    for frame_size in frame_sizes:
        if len(data) >= frame_size * 10:
            # Extract frames and check for patterns
            frames = [data[i:i+frame_size] for i in range(0, len(data) - frame_size, frame_size)]
            unique_frames = set(bytes(f) for f in frames[:100])  # Check first 100 frames
            
            if len(unique_frames) > 1:
                print(f"  Frame size {frame_size:3d}: {len(unique_frames):4d} unique patterns (first 100 frames)")
                
                # If we have good variation, this might be the right frame size
                if 10 < len(unique_frames) < 90:
                    print(f"    → Good variation - possible frame size!")
    
    print("\n" + "="*80 + "\n")


def capture_and_analyze(port, baudrate=115200, duration=3):
    """Capture data and analyze stream structure"""
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
            data = ser.read(4096)
            if data:
                all_data.extend(data)
        
        ser.close()
        
        print(f"✓ Captured {len(all_data)} bytes\n")
        
        if all_data:
            analyze_stream_structure(all_data)
            
            # Save to file for further analysis
            filename = f"jk_bms_capture_{int(time.time())}.bin"
            with open(filename, 'wb') as f:
                f.write(all_data)
            print(f"Data saved to: {filename}")
        else:
            print("❌ No data received")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='JK BMS Stream Structure Analyzer')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--duration', type=int, default=3, help='Capture duration in seconds (default: 3)')
    
    args = parser.parse_args()
    
    capture_and_analyze(args.port, args.baudrate, args.duration)
