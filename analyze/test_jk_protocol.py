#!/usr/bin/env python3
"""
Test JK BMS specific protocol via mbusd
Uses FC 0x10 (Write Multiple Registers) as trigger
"""
import socket
import sys
import struct

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.69.3"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 503
device_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1

print(f"Testing JK BMS protocol on {host}:{port} device_id={device_id}\n")

def create_jk_trigger_frame(device_id, register_addr):
    """
    Create JK BMS trigger frame using FC 0x10 (Write Multiple Registers)
    This is how the Node-RED implementation works
    """
    transaction_id = 0x0001
    protocol_id = 0x0000
    
    # FC 0x10: Write Multiple Registers
    # Register address, quantity (1), byte count (2), value (0x0000)
    function_code = 0x10
    quantity = 0x0001
    byte_count = 0x02
    value = 0x0000
    
    # Build PDU
    pdu = struct.pack('>BHHBH', function_code, register_addr, quantity, byte_count, value)
    
    # Build MBAP header
    length = len(pdu) + 1  # PDU + unit_id
    mbap = struct.pack('>HHHB', transaction_id, protocol_id, length, device_id)
    
    return mbap + pdu

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((host, port))
    print("✓ Socket connected\n")
    
    # Test the three JK BMS register addresses
    registers = [
        (0x161C, "Static Data (Trame 1)"),
        (0x161E, "Setup Data (Trame 2)"),
        (0x1620, "Live Data (Trame 3)"),
    ]
    
    for reg_addr, reg_name in registers:
        print(f"Testing {reg_name} at 0x{reg_addr:04X}:")
        frame = create_jk_trigger_frame(device_id, reg_addr)
        print(f"  Sending: {frame.hex()}")
        sock.send(frame)
        
        response = sock.recv(2048)
        print(f"  Response: {response.hex()}")
        print(f"  Length: {len(response)} bytes")
        
        if len(response) >= 8:
            trans_id, proto_id, length, unit_id = struct.unpack('>HHHB', response[:7])
            func_code = response[7] if len(response) > 7 else 0
            
            if func_code & 0x80:
                exception_code = response[8] if len(response) > 8 else 0
                print(f"  ❌ Exception: code {exception_code}")
            else:
                print(f"  ✓ SUCCESS! Function code: 0x{func_code:02X}")
                if len(response) > 8:
                    data = response[8:]
                    print(f"  Data ({len(data)} bytes): {data[:32].hex()}{'...' if len(data) > 32 else ''}")
                    
                    # Try to parse some values
                    if len(data) >= 20:
                        print(f"\n  Sample values:")
                        print(f"    Bytes 0-1:   {struct.unpack('>H', data[0:2])[0]}")
                        print(f"    Bytes 2-3:   {struct.unpack('>H', data[2:4])[0]}")
                        print(f"    Bytes 4-5:   {struct.unpack('>H', data[4:6])[0]}")
        print()
    
    sock.close()
    print("✓ Test complete")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
