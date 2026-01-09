#!/usr/bin/env python3
"""
Test if mbusd is properly forwarding Modbus requests to the serial device
"""
import argparse
import time
from pymodbus.client import ModbusTcpClient

def test_single_register(host, port, device_id, register, description):
    """Test reading a single register with detailed output"""
    print(f"\n{'='*80}")
    print(f"Testing Register {register} ({description})")
    print('='*80)
    
    client = ModbusTcpClient(host=host, port=port, timeout=10, retries=1)
    
    try:
        print(f"[1] Connecting to {host}:{port}...")
        if not client.connect():
            print("❌ TCP connection failed")
            return False
        print(f"✓ TCP connected")
        
        print(f"\n[2] Sending Modbus request: read_holding_registers(address={register}, count=1, unit={device_id})")
        start_time = time.time()
        
        try:
            result = client.read_holding_registers(register, count=1, unit=device_id)
            elapsed = time.time() - start_time
            
            print(f"Response received in {elapsed:.3f} seconds")
            
            if result.isError():
                print(f"❌ Modbus Error: {result}")
                return False
            else:
                print(f"✓ Success! Value: {result.registers[0]}")
                return True
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Exception after {elapsed:.3f} seconds: {e}")
            return False
            
    finally:
        client.close()


def test_progressive_counts(host, port, device_id):
    """Test reading progressively larger register counts"""
    print(f"\n{'='*80}")
    print(f"TESTING PROGRESSIVE REGISTER COUNTS")
    print('='*80)
    
    counts = [1, 5, 10, 25, 50, 100]
    results = {}
    
    for count in counts:
        print(f"\nTesting count={count}...", end=' ')
        client = ModbusTcpClient(host=host, port=port, timeout=10, retries=1)
        
        try:
            if client.connect():
                start_time = time.time()
                result = client.read_holding_registers(0, count=count, unit=device_id)
                elapsed = time.time() - start_time
                
                if not result.isError():
                    print(f"✓ Success in {elapsed:.3f}s")
                    results[count] = True
                else:
                    print(f"❌ Error: {result}")
                    results[count] = False
            else:
                print(f"❌ Connection failed")
                results[count] = False
        except Exception as e:
            print(f"❌ Exception: {e}")
            results[count] = False
        finally:
            client.close()
        
        time.sleep(0.5)
    
    print(f"\n{'='*80}")
    print(f"RESULTS:")
    for count, success in results.items():
        status = "✓ PASS" if success else "❌ FAIL"
        print(f"  Count {count:3d}: {status}")
    print('='*80)


def test_with_delays(host, port, device_id):
    """Test with delays between requests"""
    print(f"\n{'='*80}")
    print(f"TESTING WITH INTER-REQUEST DELAYS")
    print('='*80)
    
    delays = [0, 0.1, 0.5, 1.0, 2.0]
    test_registers = [0, 79, 108]
    
    for delay in delays:
        print(f"\nTesting with {delay}s delay between requests...")
        client = ModbusTcpClient(host=host, port=port, timeout=10, retries=1)
        
        try:
            if not client.connect():
                print(f"❌ Connection failed")
                continue
            
            success_count = 0
            for reg in test_registers:
                try:
                    result = client.read_holding_registers(reg, count=1, unit=device_id)
                    if not result.isError():
                        success_count += 1
                    time.sleep(delay)
                except:
                    pass
            
            print(f"  Success: {success_count}/{len(test_registers)} registers")
            
        finally:
            client.close()


def test_timeout_values(host, port, device_id):
    """Test different timeout values"""
    print(f"\n{'='*80}")
    print(f"TESTING DIFFERENT TIMEOUT VALUES")
    print('='*80)
    
    timeouts = [1, 3, 5, 10, 15]
    
    for timeout in timeouts:
        print(f"\nTesting with timeout={timeout}s...", end=' ')
        client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=1)
        
        try:
            if client.connect():
                start_time = time.time()
                result = client.read_holding_registers(0, count=10, unit=device_id)
                elapsed = time.time() - start_time
                
                if not result.isError():
                    print(f"✓ Success in {elapsed:.3f}s")
                else:
                    print(f"❌ Error: {result}")
            else:
                print(f"❌ Connection failed")
        except Exception as e:
            print(f"❌ Exception: {e}")
        finally:
            client.close()
        
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description='Test mbusd forwarding behavior')
    parser.add_argument('host', type=str, help='mbusd IP address')
    parser.add_argument('--port', type=int, default=502, help='mbusd TCP port (default: 502)')
    parser.add_argument('--device-id', type=int, default=0, help='Device ID (default: 0)')
    parser.add_argument('--test', choices=['single', 'counts', 'delays', 'timeouts', 'all'], 
                        default='all', help='Test type to run')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"MBUSD FORWARDING TEST")
    print(f"Target: {args.host}:{args.port}, Device ID: {args.device_id}")
    print('='*80)
    
    if args.test in ['single', 'all']:
        test_single_register(args.host, args.port, args.device_id, 0, "First register")
        test_single_register(args.host, args.port, args.device_id, 79, "Grid Frequency")
    
    if args.test in ['counts', 'all']:
        test_progressive_counts(args.host, args.port, args.device_id)
    
    if args.test in ['delays', 'all']:
        test_with_delays(args.host, args.port, args.device_id)
    
    if args.test in ['timeouts', 'all']:
        test_timeout_values(args.host, args.port, args.device_id)
    
    print(f"\n{'='*80}")
    print(f"TESTING COMPLETE")
    print('='*80)


if __name__ == "__main__":
    main()
