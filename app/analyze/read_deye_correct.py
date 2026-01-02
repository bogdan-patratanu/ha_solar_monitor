#!/usr/bin/env python3
"""
Read Deye inverter using the correct register addresses from templates
"""
import argparse
from pymodbus.client import ModbusSerialClient, ModbusTcpClient

def read_deye_correct_registers(client, device_id):
    """Read registers at the correct addresses per Deye template"""
    
    print("\n" + "="*80)
    print("DEYE INVERTER - READING REGISTER ADDRESSES")
    print("="*80 + "\n")
    
    # Read different ranges
    ranges_to_read = [
        (0, 100, "Device Info & Status (0-99)"),
        (76, 25, "Energy Counters (76-100)"),
        (108, 5, "PV Info (108-112)"),
        (150, 30, "Grid Voltages & Currents (150-179)"),
        (183, 10, "Battery Info (183-192)"),
    ]
    
    all_data = {}
    
    for start, count, description in ranges_to_read:
        print(f"\nReading {description}...")
        try:
            result = client.read_holding_registers(address=start, count=count, device_id=device_id)
            if not result.isError():
                for i, val in enumerate(result.registers):
                    all_data[start + i] = val
                print(f"✓ Read {len(result.registers)} registers")
            else:
                print(f"✗ Error: {result}")
        except Exception as e:
            print(f"✗ Exception: {e}")
    
    # Now parse according to template
    print("\n" + "="*80)
    print("PARSED VALUES (per Deye template)")
    print("="*80 + "\n")
    
    # Grid Frequency (register 79, factor 0.01)
    if 79 in all_data:
        freq = all_data[79] * 0.01
        print(f"Grid Frequency (R79):           {all_data[79]:5d} -> {freq:6.2f} Hz")
    
    # Daily Grid Import (register 76, factor 0.1)
    if 76 in all_data:
        daily_import = all_data[76] * 0.1
        print(f"Daily Grid Import (R76):        {all_data[76]:5d} -> {daily_import:6.1f} kWh")
    
    # Daily Energy (register 108, factor 0.1)
    if 108 in all_data:
        daily_energy = all_data[108] * 0.1
        print(f"Daily Energy (R108):            {all_data[108]:5d} -> {daily_energy:6.1f} kWh")
    
    # PV1 Voltage (register 109, factor 0.1)
    if 109 in all_data:
        pv1_v = all_data[109] * 0.1
        print(f"PV1 Voltage (R109):             {all_data[109]:5d} -> {pv1_v:6.1f} V")
    
    # PV1 Current (register 110, factor 0.1)
    if 110 in all_data:
        pv1_i = all_data[110] * 0.1
        print(f"PV1 Current (R110):             {all_data[110]:5d} -> {pv1_i:6.1f} A")
    
    # PV2 Voltage (register 111, factor 0.1)
    if 111 in all_data:
        pv2_v = all_data[111] * 0.1
        print(f"PV2 Voltage (R111):             {all_data[111]:5d} -> {pv2_v:6.1f} V")
    
    # PV2 Current (register 112, factor 0.1)
    if 112 in all_data:
        pv2_i = all_data[112] * 0.1
        print(f"PV2 Current (R112):             {all_data[112]:5d} -> {pv2_i:6.1f} A")
    
    print("\n" + "-"*80)
    print("GRID VOLTAGES (3-phase)")
    print("-"*80)
    
    # Grid Voltages L1, L2, L3 (registers 150-152, factor 0.1)
    for i, phase in enumerate(['L1', 'L2', 'L3']):
        reg = 150 + i
        if reg in all_data:
            voltage = all_data[reg] * 0.1
            print(f"Grid Voltage {phase} (R{reg}):       {all_data[reg]:5d} -> {voltage:6.1f} V")
    
    print("\n" + "-"*80)
    print("GRID CURRENTS (3-phase)")
    print("-"*80)
    
    # Grid Currents L1, L2, L3 (registers 160-162, factor 0.01)
    for i, phase in enumerate(['L1', 'L2', 'L3']):
        reg = 160 + i
        if reg in all_data:
            current = all_data[reg] * 0.01
            print(f"Grid Current {phase} (R{reg}):       {all_data[reg]:5d} -> {current:6.2f} A")
    
    print("\n" + "-"*80)
    print("GRID POWER (3-phase)")
    print("-"*80)
    
    # Grid Power L1, L2, L3 (registers 167-169, factor -1)
    for i, phase in enumerate(['L1', 'L2', 'L3']):
        reg = 167 + i
        if reg in all_data:
            power_raw = all_data[reg]
            power_signed = power_raw if power_raw < 32768 else power_raw - 65536
            power = power_signed * -1
            print(f"Grid Power {phase} (R{reg}):         {all_data[reg]:5d} (signed: {power_signed:6d}) -> {power:6d} W")
    
    print("\n" + "-"*80)
    print("BATTERY INFO")
    print("-"*80)
    
    # Battery Voltage (register 183, factor 0.01)
    if 183 in all_data:
        batt_v = all_data[183] * 0.01
        print(f"Battery Voltage (R183):         {all_data[183]:5d} -> {batt_v:6.2f} V")
    
    # Battery SOC (register 184, factor 1)
    if 184 in all_data:
        batt_soc = all_data[184]
        print(f"Battery SOC (R184):             {all_data[184]:5d} -> {batt_soc:6d} %")
    
    # Battery Power (register 190, factor -1)
    if 190 in all_data:
        batt_p_raw = all_data[190]
        batt_p_signed = batt_p_raw if batt_p_raw < 32768 else batt_p_raw - 65536
        batt_p = batt_p_signed * -1
        print(f"Battery Power (R190):           {all_data[190]:5d} (signed: {batt_p_signed:6d}) -> {batt_p:6d} W")
    
    print("\n" + "="*80 + "\n")


def main_rtu(port, baudrate, device_id):
    print(f"\nAttempting RTU connection to {port} at {baudrate} baud with device_id={device_id}")
    client = ModbusSerialClient(port=port, baudrate=baudrate, timeout=1.0, retries=3, bytesize=8, parity='N', stopbits=1)
    try:
        print("Connecting...")
        if not client.connect():
            print("❌ Failed to connect to serial port")
            print("\nTroubleshooting tips:")
            print("  1. Check port exists: ls -l", port)
            print("  2. Check permissions: sudo chmod 666", port)
            print("  3. Verify no other process is using the port")
            return
        print(f"✓ Connected to {port} at {baudrate} baud (device_id: {device_id})")
        read_deye_correct_registers(client, device_id)
    except Exception as e:
        print(f"❌ Exception during RTU connection: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


def main_tcp(host, port, device_id):
    print(f"\nAttempting TCP connection to {host}:{port} with device_id={device_id}")
    client = ModbusTcpClient(host=host, port=port, timeout=5, retries=3)
    try:
        print("Connecting...")
        if not client.connect():
            print("❌ Failed to establish TCP connection")
            print("\nTroubleshooting tips:")
            print("  1. Check mbusd is running: systemctl status mbusd")
            print("  2. Verify port 502 is listening: netstat -tlnp | grep 502")
            print("  3. Try device_id=1 if using default 0")
            return
        
        if not client.is_socket_open():
            print("❌ Socket is not open")
            return
            
        print(f"✓ Connected to {host}:{port} (device_id: {device_id})")
        read_deye_correct_registers(client, device_id)
    except Exception as e:
        print(f"❌ Exception during TCP connection: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Read Deye Inverter at Correct Register Addresses')
    parser.add_argument('target', type=str, help='IP address (TCP) or serial port (RTU)')
    parser.add_argument('--mode', choices=['tcp', 'rtu'], default='rtu', help='Connection mode (default: rtu)')
    parser.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('--baudrate', type=int, default=9600, help='RTU baudrate (default: 9600)')
    parser.add_argument('--device-id', type=int, default=1, help='Device/Unit ID (default: 1, Deye standard)')
    args = parser.parse_args()
    
    if args.mode == 'tcp':
        main_tcp(args.target, args.port, args.device_id)
    else:
        main_rtu(args.target, args.baudrate, args.device_id)
