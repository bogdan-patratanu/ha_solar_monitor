#!/usr/bin/env python3
"""
Analyze and identify Modbus devices (Deye Inverter or JK BMS)
"""
import argparse
import logging
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ConnectionException

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def analyze_deye_inverter(registers):
    """Analyze registers as Deye 3-phase inverter"""
    print("\n" + "="*80)
    print("DEYE 3-PHASE INVERTER ANALYSIS")
    print("="*80 + "\n")
    
    # Common Deye register mappings (may vary by model)
    mappings = {
        0: ("Device Type/Model", lambda v: v),
        1: ("Communication Protocol Version", lambda v: f"{v >> 8}.{v & 0xFF}"),
        2: ("Firmware Version", lambda v: f"{v >> 8}.{v & 0xFF}"),
        3-7: ("Serial Number", lambda regs: ''.join(chr(r >> 8) + chr(r & 0xFF) for r in regs if r != 0)),
        
        # Power measurements (typical locations, may vary)
        11: ("Status/State", lambda v: v),
        12: ("AC Power Phase A", lambda v: (v if v < 32768 else v - 65536) / 10, "W"),
        13: ("AC Power Phase B", lambda v: (v if v < 32768 else v - 65536) / 10, "W"),
        14: ("AC Power Phase C", lambda v: (v if v < 32768 else v - 65536) / 10, "W"),
        
        # Voltage measurements
        18: ("AC Voltage Phase A", lambda v: v / 10, "V"),
        19: ("AC Voltage Phase B", lambda v: v / 10, "V"),
        20: ("AC Voltage Phase C", lambda v: v / 10, "V"),
        
        # Current measurements
        24: ("AC Current Phase A", lambda v: v / 10, "A"),
        25: ("AC Current Phase B", lambda v: v / 10, "A"),
        26: ("AC Current Phase C", lambda v: v / 10, "A"),
        
        # DC side
        60: ("PV1 Voltage", lambda v: v / 10, "V"),
        61: ("PV1 Current", lambda v: v / 10, "A"),
        62: ("PV2 Voltage", lambda v: v / 10, "V"),
        63: ("PV2 Current", lambda v: v / 10, "A"),
        
        # Energy counters
        75: ("Daily Energy Production", lambda v: v / 10, "kWh"),
        76: ("Total Energy Production Low", lambda v: v, "kWh"),
        77: ("Total Energy Production High", lambda v: v, "kWh"),
        
        79: ("Grid Frequency", lambda v: v / 100, "Hz"),
        
        # Temperature
        90: ("Inverter Temperature", lambda v: (v if v < 32768 else v - 65536) / 10, "°C"),
    }
    
    # Device identification
    if len(registers) > 7:
        serial = ''.join(chr(registers[i] >> 8) + chr(registers[i] & 0xFF) 
                        for i in range(3, 8) if registers[i] != 0)
        print(f"Serial Number: {serial}")
    
    if len(registers) > 2:
        fw_ver = f"{registers[2] >> 8}.{registers[2] & 0xFF}"
        print(f"Firmware Version: {fw_ver}")
    
    print("\n" + "-"*80)
    print(f"{'Register':<12} {'Description':<30} {'Value':<15} {'Unit':<10}")
    print("-"*80)
    
    # Parse known registers
    for reg_addr, info in mappings.items():
        if isinstance(reg_addr, range):
            continue
        if reg_addr < len(registers):
            desc = info[0]
            func = info[1]
            unit = info[2] if len(info) > 2 else ""
            
            try:
                value = func(registers[reg_addr])
                if isinstance(value, float):
                    print(f"{reg_addr:<12} {desc:<30} {value:<15.2f} {unit:<10}")
                else:
                    print(f"{reg_addr:<12} {desc:<30} {value:<15} {unit:<10}")
            except:
                pass
    
    # Calculate total power if available
    if len(registers) > 14:
        try:
            power_a = (registers[12] if registers[12] < 32768 else registers[12] - 65536) / 10
            power_b = (registers[13] if registers[13] < 32768 else registers[13] - 65536) / 10
            power_c = (registers[14] if registers[14] < 32768 else registers[14] - 65536) / 10
            total_power = power_a + power_b + power_c
            print(f"\n{'TOTAL':<12} {'Total AC Power':<30} {total_power:<15.2f} {'W':<10}")
        except:
            pass
    
    print("\n" + "="*80 + "\n")


def analyze_jk_bms(registers):
    """Analyze registers as JK BMS"""
    print("\n" + "="*80)
    print("JK BMS ANALYSIS")
    print("="*80 + "\n")
    
    # JK BMS typical register mappings
    mappings = {
        0: ("Device Type", lambda v: v),
        1: ("Protocol Version", lambda v: v),
        
        # Voltage measurements
        10: ("Total Voltage", lambda v: v / 100, "V"),
        11: ("Current", lambda v: (v if v < 32768 else v - 65536) / 100, "A"),
        12: ("Battery SOC", lambda v: v, "%"),
        
        # Cell voltages (typically starting around register 20-40)
        20: ("Cell 1 Voltage", lambda v: v, "mV"),
        21: ("Cell 2 Voltage", lambda v: v, "mV"),
        22: ("Cell 3 Voltage", lambda v: v, "mV"),
        23: ("Cell 4 Voltage", lambda v: v, "mV"),
        
        # Temperatures
        60: ("Temperature 1", lambda v: (v if v < 32768 else v - 65536) / 10, "°C"),
        61: ("Temperature 2", lambda v: (v if v < 32768 else v - 65536) / 10, "°C"),
        
        # Status and protection
        70: ("Protection Status", lambda v: f"0x{v:04x}"),
        71: ("Charge/Discharge Status", lambda v: v),
        
        # Capacity
        75: ("Remaining Capacity", lambda v: v / 100, "Ah"),
        76: ("Total Capacity", lambda v: v / 100, "Ah"),
        
        # Cycle count
        80: ("Cycle Count", lambda v: v),
    }
    
    print(f"{'Register':<12} {'Description':<30} {'Value':<15} {'Unit':<10}")
    print("-"*80)
    
    for reg_addr, info in mappings.items():
        if reg_addr < len(registers):
            desc = info[0]
            func = info[1]
            unit = info[2] if len(info) > 2 else ""
            
            try:
                value = func(registers[reg_addr])
                if isinstance(value, float):
                    print(f"{reg_addr:<12} {desc:<30} {value:<15.2f} {unit:<10}")
                else:
                    print(f"{reg_addr:<12} {desc:<30} {value:<15} {unit:<10}")
            except:
                pass
    
    # Calculate power if voltage and current available
    if len(registers) > 11:
        try:
            voltage = registers[10] / 100
            current = (registers[11] if registers[11] < 32768 else registers[11] - 65536) / 100
            power = voltage * current
            print(f"\n{'CALCULATED':<12} {'Power':<30} {power:<15.2f} {'W':<10}")
        except:
            pass
    
    print("\n" + "="*80 + "\n")


def identify_device(registers):
    """Try to identify which device type based on register patterns"""
    print("\n" + "="*80)
    print("DEVICE IDENTIFICATION")
    print("="*80 + "\n")
    
    confidence_deye = 0
    confidence_jk = 0
    
    # Check for Deye indicators
    if len(registers) > 7:
        # Deye typically has ASCII serial number in registers 3-7
        ascii_count = 0
        for i in range(3, min(8, len(registers))):
            high = registers[i] >> 8
            low = registers[i] & 0xFF
            if 32 <= high < 127 and 32 <= low < 127:
                ascii_count += 1
        
        if ascii_count >= 3:
            confidence_deye += 40
            print(f"✓ Found ASCII serial number pattern (Deye indicator)")
    
    # Check for typical Deye firmware version format
    if len(registers) > 2 and registers[2] > 0 and registers[2] < 0x0FFF:
        confidence_deye += 20
        print(f"✓ Firmware version format matches Deye")
    
    # Check for three-phase power values (negative values indicate consumption)
    if len(registers) > 14:
        signed_values = sum(1 for i in [12, 13, 14] if registers[i] > 32768)
        if signed_values >= 1:
            confidence_deye += 20
            print(f"✓ Found signed power values (3-phase indicator)")
    
    # Check for JK BMS indicators
    if len(registers) > 12:
        # JK BMS typically has SOC as percentage (0-100)
        if 0 <= registers[12] <= 100:
            confidence_jk += 30
            print(f"✓ Register 12 is valid SOC percentage (JK indicator)")
    
    # Check for cell voltage patterns (typically 2500-4200 mV)
    if len(registers) > 23:
        cell_voltage_count = 0
        for i in range(20, min(24, len(registers))):
            if 2500 <= registers[i] <= 4200:
                cell_voltage_count += 1
        
        if cell_voltage_count >= 2:
            confidence_jk += 40
            print(f"✓ Found valid cell voltage values (JK BMS indicator)")
    
    print(f"\nConfidence Scores:")
    print(f"  Deye 3-Phase Inverter: {confidence_deye}%")
    print(f"  JK BMS: {confidence_jk}%")
    
    if confidence_deye > confidence_jk:
        print(f"\n→ Most likely: DEYE 3-PHASE INVERTER")
        return "deye"
    elif confidence_jk > confidence_deye:
        print(f"\n→ Most likely: JK BMS")
        return "jk"
    else:
        print(f"\n→ Unable to determine device type with confidence")
        return "unknown"


def analyze_device_rtu(port: str, baudrate: int, device_id: int, count: int = 100):
    """Analyze RTU Modbus device"""
    print(f"\nConnecting to {port} at {baudrate} baud (device_id: {device_id})...")
    
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
        
        print("✓ Connected\n")
        
        result = client.read_holding_registers(0, count=count, device_id=device_id)
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return
        
        registers = result.registers
        
        # Identify device
        device_type = identify_device(registers)
        
        # Analyze based on type
        if device_type == "deye" or device_type == "unknown":
            analyze_deye_inverter(registers)
        
        if device_type == "jk" or device_type == "unknown":
            analyze_jk_bms(registers)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


def analyze_device_tcp(host: str, port: int, device_id: int, count: int = 100):
    """Analyze TCP Modbus device"""
    print(f"\nConnecting to {host}:{port} (device_id: {device_id})...")
    
    client = ModbusTcpClient(host=host, port=port, timeout=3, retries=3)
    
    try:
        if not client.connect():
            print("❌ Failed to connect")
            return
        
        print("✓ Connected\n")
        
        result = client.read_holding_registers(0, count=count, device_id=device_id)
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return
        
        registers = result.registers
        
        # Identify device
        device_type = identify_device(registers)
        
        # Analyze based on type
        if device_type == "deye" or device_type == "unknown":
            analyze_deye_inverter(registers)
        
        if device_type == "jk" or device_type == "unknown":
            analyze_jk_bms(registers)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze Modbus Device (Deye Inverter or JK BMS)')
    parser.add_argument('target', type=str, help='IP address (TCP) or serial port (RTU)')
    parser.add_argument('--mode', choices=['tcp', 'rtu'], default='rtu', help='Connection mode (default: rtu)')
    parser.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('--baudrate', type=int, default=9600, help='RTU baudrate (default: 9600)')
    parser.add_argument('--device-id', type=int, default=0, help='Device/Unit ID (default: 0)')
    parser.add_argument('--count', type=int, default=100, help='Number of registers to read (default: 100)')
    args = parser.parse_args()
    
    if args.mode == 'tcp':
        analyze_device_tcp(args.target, args.port, args.device_id, args.count)
    else:
        analyze_device_rtu(args.target, args.baudrate, args.device_id, args.count)
