#!/usr/bin/env python3
"""
Test direct communication with mbusd to verify it's working
"""
import socket
import sys
import struct

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.69.3"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 503

print(f"Testing direct socket connection to {host}:{port}\n")

# Create raw Modbus TCP frame
# Format: [Transaction ID (2), Protocol ID (2), Length (2), Unit ID (1), Function Code (1), ...]

def create_modbus_tcp_frame(device_id, function_code, register_addr, count):
    """Create a Modbus TCP frame"""
    transaction_id = 0x0001
    protocol_id = 0x0000  # Modbus protocol
    
    # PDU: function_code + register_high + register_low + count_high + count_low
    pdu = struct.pack('>BBHH', function_code, 0, register_addr, count)
    
    # MBAP Header: transaction_id + protocol_id + length + unit_id
    length = len(pdu) + 1  # PDU + unit_id
    mbap = struct.pack('>HHHB', transaction_id, protocol_id, length, device_id)
    
    return mbap + pdu

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    sock.connect((host, port))
    print("✓ Socket connected\n")
    
    # Test 1: Read holding register 0, count 1, device 1
    print("Test 1: Read Holding Register 0 (device_id=1)")
    frame = create_modbus_tcp_frame(device_id=1, function_code=0x03, register_addr=0, count=1)
    print(f"  Sending: {frame.hex()}")
    sock.send(frame)
    
    response = sock.recv(1024)
    print(f"  Response: {response.hex()}")
    print(f"  Length: {len(response)} bytes")
    
    if len(response) >= 8:
        # Parse MBAP header
        trans_id, proto_id, length, unit_id = struct.unpack('>HHHB', response[:7])
        func_code = response[7] if len(response) > 7 else 0
        print(f"  Parsed: trans_id={trans_id}, proto_id={proto_id}, length={length}, unit_id={unit_id}, func_code={func_code}")
        
        if func_code & 0x80:
            exception_code = response[8] if len(response) > 8 else 0
            print(f"  ❌ Exception response! Code: {exception_code}")
            print(f"     Exception codes: 1=Illegal Function, 2=Illegal Address, 3=Illegal Value, 4=Device Failure")
        else:
            print(f"  ✓ Success!")
            if len(response) > 8:
                data = response[8:]
                print(f"  Data: {data.hex()}")
    
    print()
    
    # Test 2: Try device_id 0 (broadcast/master)
    print("Test 2: Read Holding Register 0 (device_id=0)")
    frame = create_modbus_tcp_frame(device_id=0, function_code=0x03, register_addr=0, count=1)
    print(f"  Sending: {frame.hex()}")
    sock.send(frame)
    
    response = sock.recv(1024)
    print(f"  Response: {response.hex()}")
    print()
    
    # Test 3: Scan device IDs
    print("Test 3: Quick scan of device IDs 1-5")
    for dev_id in range(1, 6):
        frame = create_modbus_tcp_frame(device_id=dev_id, function_code=0x03, register_addr=0, count=1)
        sock.send(frame)
        response = sock.recv(1024)
        
        if len(response) >= 9:
            func_code = response[8]
            if func_code & 0x80:
                exception_code = response[9] if len(response) > 9 else 0
                print(f"  Device {dev_id}: Exception code {exception_code}")
            else:
                print(f"  Device {dev_id}: ✓ SUCCESS!")
        else:
            print(f"  Device {dev_id}: No response")
    
    sock.close()
    print("\n✓ Test complete")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
