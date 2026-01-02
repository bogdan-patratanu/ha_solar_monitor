#!/usr/bin/env python3
"""
Debug mbusd connection to Deye inverter
Tests various device IDs, timeouts, and connection parameters
"""
import argparse
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

def test_connection(host, port, device_id, timeout=3):
    """Test basic connection to mbusd"""
    print(f"\n{'='*80}")
    print(f"Testing connection to {host}:{port} with device_id={device_id}, timeout={timeout}s")
    print('='*80)
    
    client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=3)
    
    try:
        # Test connection
        print(f"[1/4] Attempting to connect...")
        if not client.connect():
            print("❌ Failed to establish TCP connection")
            return False
        print(f"✓ TCP connection established")
        
        # Test if socket is actually connected
        print(f"\n[2/4] Verifying socket connection...")
        if not client.is_socket_open():
            print("❌ Socket is not open")
            return False
        print(f"✓ Socket is open and ready")
        
        # Try a simple read operation
        print(f"\n[3/4] Testing Modbus read (register 0, count 1)...")
        try:
            result = client.read_holding_registers(0, count=1, unit=device_id)
            if result.isError():
                print(f"❌ Modbus error: {result}")
                return False
            print(f"✓ Successfully read register 0: {result.registers[0]}")
        except ModbusException as e:
            print(f"❌ Modbus exception: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected exception: {e}")
            return False
        
        # Try reading a known Deye register
        print(f"\n[4/4] Testing Deye-specific register (R79 - Grid Frequency)...")
        try:
            result = client.read_holding_registers(79, count=1, unit=device_id)
            if result.isError():
                print(f"❌ Modbus error: {result}")
            else:
                freq = result.registers[0] * 0.01
                print(f"✓ Successfully read R79: {result.registers[0]} -> {freq:.2f} Hz")
        except Exception as e:
            print(f"⚠ Exception reading R79: {e}")
        
        print(f"\n{'='*80}")
        print(f"✓ CONNECTION SUCCESSFUL with device_id={device_id}")
        print('='*80)
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    finally:
        client.close()


def scan_device_ids(host, port, max_id=10):
    """Scan for responsive device IDs"""
    print(f"\n{'='*80}")
    print(f"SCANNING DEVICE IDs (0-{max_id}) on {host}:{port}")
    print('='*80)
    
    responsive_ids = []
    
    for device_id in range(max_id + 1):
        print(f"\nTesting device_id={device_id}...", end=' ')
        client = ModbusTcpClient(host=host, port=port, timeout=2, retries=1)
        
        try:
            if client.connect():
                result = client.read_holding_registers(0, count=1, unit=device_id)
                if not result.isError():
                    print(f"✓ RESPONSIVE")
                    responsive_ids.append(device_id)
                else:
                    print(f"✗ Error: {result}")
            else:
                print(f"✗ Connection failed")
        except Exception as e:
            print(f"✗ Exception: {e}")
        finally:
            client.close()
        
        time.sleep(0.1)  # Small delay between attempts
    
    print(f"\n{'='*80}")
    if responsive_ids:
        print(f"✓ Found {len(responsive_ids)} responsive device ID(s): {responsive_ids}")
    else:
        print(f"❌ No responsive device IDs found")
    print('='*80)
    
    return responsive_ids


def compare_rtu_vs_tcp(serial_port, tcp_host, tcp_port, device_id, baudrate=9600):
    """Compare RTU vs TCP responses for the same register"""
    from pymodbus.client import ModbusSerialClient
    
    print(f"\n{'='*80}")
    print(f"COMPARING RTU vs TCP RESPONSES")
    print('='*80)
    
    test_registers = [0, 79, 108, 109, 150, 183]
    
    # Test RTU
    print(f"\n[RTU] Testing {serial_port} at {baudrate} baud...")
    rtu_client = ModbusSerialClient(port=serial_port, baudrate=baudrate, timeout=1.0, 
                                     retries=3, bytesize=8, parity='N', stopbits=1)
    rtu_results = {}
    
    try:
        if rtu_client.connect():
            print(f"✓ RTU connected")
            for reg in test_registers:
                try:
                    result = rtu_client.read_holding_registers(reg, count=1, unit=device_id)
                    if not result.isError():
                        rtu_results[reg] = result.registers[0]
                        print(f"  R{reg}: {result.registers[0]}")
                    else:
                        print(f"  R{reg}: Error - {result}")
                except Exception as e:
                    print(f"  R{reg}: Exception - {e}")
        else:
            print(f"❌ RTU connection failed")
    finally:
        rtu_client.close()
    
    # Test TCP
    print(f"\n[TCP] Testing {tcp_host}:{tcp_port}...")
    tcp_client = ModbusTcpClient(host=tcp_host, port=tcp_port, timeout=3, retries=3)
    tcp_results = {}
    
    try:
        if tcp_client.connect():
            print(f"✓ TCP connected")
            for reg in test_registers:
                try:
                    result = tcp_client.read_holding_registers(reg, count=1, unit=device_id)
                    if not result.isError():
                        tcp_results[reg] = result.registers[0]
                        print(f"  R{reg}: {result.registers[0]}")
                    else:
                        print(f"  R{reg}: Error - {result}")
                except Exception as e:
                    print(f"  R{reg}: Exception - {e}")
        else:
            print(f"❌ TCP connection failed")
    finally:
        tcp_client.close()
    
    # Compare
    print(f"\n{'='*80}")
    print(f"COMPARISON RESULTS")
    print('='*80)
    print(f"{'Register':<12} {'RTU Value':<15} {'TCP Value':<15} {'Match'}")
    print('-'*80)
    
    for reg in test_registers:
        rtu_val = rtu_results.get(reg, 'N/A')
        tcp_val = tcp_results.get(reg, 'N/A')
        match = '✓' if rtu_val == tcp_val and rtu_val != 'N/A' else '✗'
        print(f"R{reg:<11} {str(rtu_val):<15} {str(tcp_val):<15} {match}")


def main():
    parser = argparse.ArgumentParser(description='Debug mbusd connection to Deye inverter')
    parser.add_argument('host', type=str, help='mbusd IP address')
    parser.add_argument('--port', type=int, default=502, help='mbusd TCP port (default: 502)')
    parser.add_argument('--device-id', type=int, default=None, help='Device ID to test (default: scan 0-10)')
    parser.add_argument('--scan', action='store_true', help='Scan for responsive device IDs')
    parser.add_argument('--compare', type=str, help='Compare with RTU (provide serial port path)')
    parser.add_argument('--baudrate', type=int, default=9600, help='RTU baudrate for comparison (default: 9600)')
    parser.add_argument('--timeout', type=int, default=3, help='TCP timeout in seconds (default: 3)')
    
    args = parser.parse_args()
    
    if args.scan or args.device_id is None:
        # Scan for device IDs
        responsive_ids = scan_device_ids(args.host, args.port)
        
        # Test each responsive ID
        for device_id in responsive_ids:
            test_connection(args.host, args.port, device_id, args.timeout)
    else:
        # Test specific device ID
        test_connection(args.host, args.port, args.device_id, args.timeout)
    
    # Compare RTU vs TCP if requested
    if args.compare:
        device_id = args.device_id if args.device_id is not None else 1
        compare_rtu_vs_tcp(args.compare, args.host, args.port, device_id, args.baudrate)


if __name__ == "__main__":
    main()
