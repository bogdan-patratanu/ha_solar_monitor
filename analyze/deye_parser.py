#!/usr/bin/env python3
"""
Deye 3-Phase Inverter Parser
Based on actual register analysis
"""
import argparse
import logging
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def parse_deye_registers(registers):
    """Parse Deye inverter registers with correct scaling"""
    
    print("\n" + "="*80)
    print("DEYE 3-PHASE INVERTER - DETAILED ANALYSIS")
    print("="*80 + "\n")
    
    # Device Information
    print("DEVICE INFORMATION:")
    print("-" * 80)
    
    if len(registers) > 0:
        print(f"Device Type/Model:        {registers[0]}")
    
    if len(registers) > 1:
        print(f"Protocol Version:         {registers[1]}")
    
    if len(registers) > 2:
        fw_high = registers[2] >> 8
        fw_low = registers[2] & 0xFF
        print(f"Firmware Version:         {fw_high}.{fw_low}")
    
    # Serial Number from ASCII registers
    if len(registers) > 7:
        serial_chars = []
        for i in range(3, 8):
            if registers[i] != 0:
                high = registers[i] >> 8
                low = registers[i] & 0xFF
                if 32 <= high < 127:
                    serial_chars.append(chr(high))
                if 32 <= low < 127:
                    serial_chars.append(chr(low))
        serial = ''.join(serial_chars)
        print(f"Serial Number:            {serial}")
    
    # Status and operational data
    print("\n" + "="*80)
    print("OPERATIONAL STATUS:")
    print("-" * 80)
    
    if len(registers) > 11:
        status = registers[11]
        print(f"Status Register:          {status} (0x{status:04x})")
        # Decode status bits if known
    
    # Power measurements (registers 12-14 appear to be signed values)
    print("\n" + "="*80)
    print("POWER MEASUREMENTS:")
    print("-" * 80)
    
    if len(registers) > 14:
        # These are signed int16 values, likely in watts or need scaling
        power_a_raw = registers[12]
        power_b_raw = registers[13]
        power_c_raw = registers[14]
        
        # Convert to signed
        power_a = power_a_raw if power_a_raw < 32768 else power_a_raw - 65536
        power_b = power_b_raw if power_b_raw < 32768 else power_b_raw - 65536
        power_c = power_c_raw if power_c_raw < 32768 else power_c_raw - 65536
        
        # Try different scaling factors
        print(f"Phase A Power (raw):      {power_a} W")
        print(f"Phase A Power (/10):      {power_a/10:.1f} W")
        print(f"Phase B Power (raw):      {power_b} W")
        print(f"Phase B Power (/10):      {power_b/10:.1f} W")
        print(f"Phase C Power (raw):      {power_c} W")
        print(f"Phase C Power (/10):      {power_c/10:.1f} W")
        
        total_power = power_a + power_b + power_c
        print(f"\nTotal Power (raw):        {total_power} W")
        print(f"Total Power (/10):        {total_power/10:.1f} W")
    
    # Voltage measurements (registers 18-20)
    print("\n" + "="*80)
    print("VOLTAGE MEASUREMENTS:")
    print("-" * 80)
    
    if len(registers) > 20:
        # Try different scaling factors
        for i, phase in enumerate(['A', 'B', 'C']):
            reg_idx = 18 + i
            if reg_idx < len(registers):
                val = registers[reg_idx]
                print(f"Phase {phase} Voltage (raw):    {val}")
                print(f"Phase {phase} Voltage (/10):    {val/10:.1f} V")
                print(f"Phase {phase} Voltage (/100):   {val/100:.2f} V")
                print()
    
    # Current measurements (registers 24-26)
    print("="*80)
    print("CURRENT MEASUREMENTS:")
    print("-" * 80)
    
    if len(registers) > 26:
        for i, phase in enumerate(['A', 'B', 'C']):
            reg_idx = 24 + i
            if reg_idx < len(registers):
                val = registers[reg_idx]
                print(f"Phase {phase} Current (raw):    {val}")
                print(f"Phase {phase} Current (/10):    {val/10:.2f} A")
                print(f"Phase {phase} Current (/100):   {val/100:.3f} A")
                print()
    
    # PV (DC) side measurements
    print("="*80)
    print("PV/DC MEASUREMENTS:")
    print("-" * 80)
    
    if len(registers) > 63:
        for pv_num in [1, 2]:
            v_idx = 60 + (pv_num - 1) * 2
            i_idx = 61 + (pv_num - 1) * 2
            
            if v_idx < len(registers) and i_idx < len(registers):
                voltage = registers[v_idx]
                current = registers[i_idx]
                
                print(f"PV{pv_num} Voltage (raw):       {voltage}")
                print(f"PV{pv_num} Voltage (/10):       {voltage/10:.1f} V")
                print(f"PV{pv_num} Voltage (/100):      {voltage/100:.2f} V")
                print(f"PV{pv_num} Current (raw):       {current}")
                print(f"PV{pv_num} Current (/10):       {current/10:.2f} A")
                print(f"PV{pv_num} Current (/100):      {current/100:.3f} A")
                print()
    
    # Energy counters
    print("="*80)
    print("ENERGY COUNTERS:")
    print("-" * 80)
    
    if len(registers) > 76:
        daily = registers[75]
        total_low = registers[76]
        total_high = registers[77] if len(registers) > 77 else 0
        
        print(f"Daily Energy (raw):       {daily}")
        print(f"Daily Energy (/10):       {daily/10:.1f} kWh")
        print(f"Daily Energy (/100):      {daily/100:.2f} kWh")
        print(f"Total Energy Low:         {total_low}")
        print(f"Total Energy High:        {total_high}")
        
        if total_high != 65535:  # 65535 often means "not used"
            total = (total_high << 16) + total_low
            print(f"Total Energy Combined:    {total} kWh")
    
    # Grid frequency
    print("\n" + "="*80)
    print("GRID PARAMETERS:")
    print("-" * 80)
    
    if len(registers) > 79:
        freq = registers[79]
        print(f"Grid Frequency (raw):     {freq}")
        print(f"Grid Frequency (/10):     {freq/10:.2f} Hz")
        print(f"Grid Frequency (/100):    {freq/100:.3f} Hz")
    
    # Temperature
    print("\n" + "="*80)
    print("TEMPERATURE:")
    print("-" * 80)
    
    if len(registers) > 90:
        temp_raw = registers[90]
        temp_signed = temp_raw if temp_raw < 32768 else temp_raw - 65536
        print(f"Temperature (raw):        {temp_raw}")
        print(f"Temperature (signed):     {temp_signed}")
        print(f"Temperature (/10):        {temp_signed/10:.1f} °C")
    
    # Additional interesting registers
    print("\n" + "="*80)
    print("OTHER REGISTERS:")
    print("-" * 80)
    
    interesting = [22, 23, 28, 29, 30, 33, 60, 61, 62, 63, 64, 99]
    for reg in interesting:
        if reg < len(registers) and registers[reg] != 0:
            val = registers[reg]
            signed = val if val < 32768 else val - 65536
            print(f"Register {reg:3d}:            {val:5d} (0x{val:04x}) signed: {signed:6d}")
    
    print("\n" + "="*80 + "\n")


def test_connection(host: str, port: int):
    """Test Modbus TCP connection"""
    print(f"Testing connection to {host}:{port}...")
    client = ModbusTcpClient(host=host, port=port, timeout=5)
    try:
        if client.connect():
            print("✅ Connection successful")
            client.close()
            return True
        print("❌ Connection failed")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def read_and_parse_rtu(port: str, baudrate: int, device_id: int, count: int = 100):
    """Read from RTU and parse"""
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=1.0,
        retries=3,
        bytesize=8,
        parity='N',
        stopbits=1
    )
    
    try:
        if not client.connect():
            print("❌ Failed to connect")
            return
        
        print(f"✓ Connected to {port} at {baudrate} baud (device_id: {device_id})\n")
        
        result = client.read_holding_registers(0, count=count, device_id=device_id)
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return
        
        parse_deye_registers(result.registers)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


def read_and_parse_tcp(host: str, port: int, device_id: int, count: int = 100):
    """Read from TCP and parse"""
    print(f"Connecting to {host}:{port} with timeout=5s...")
    client = ModbusTcpClient(host=host, port=port, timeout=5, retries=3)
    
    try:
        if not client.connect():
            print("❌ Failed to connect")
            return
        
        print(f"✓ Connected to {host}:{port} (device_id: {device_id})\n")
        
        result = client.read_holding_registers(0, count=count, device_id=device_id)
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return
        
        parse_deye_registers(result.registers)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Deye Inverter Parser with Multiple Scaling Options')
    parser.add_argument('target', type=str, help='IP address (TCP) or serial port (RTU)')
    parser.add_argument('--mode', choices=['tcp', 'rtu'], default='rtu', help='Connection mode (default: rtu)')
    parser.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('--baudrate', type=int, default=9600, help='RTU baudrate (default: 9600)')
    parser.add_argument('--device-id', type=int, default=1, help='Device/Unit ID (default: 1)')
    parser.add_argument('--count', type=int, default=100, help='Number of registers to read (default: 100)')
    parser.add_argument('--test', action='store_true', help='Only test connection without reading registers')
    args = parser.parse_args()
    
    if args.mode == 'tcp' and args.test:
        test_connection(args.target, args.port)
        exit(0)
    
    if args.mode == 'tcp':
        read_and_parse_tcp(args.target, args.port, args.device_id, args.count)
    else:
        read_and_parse_rtu(args.target, args.baudrate, args.device_id, args.count)
