#!/usr/bin/env python3
"""
Read and display registers from Modbus devices (TCP or RTU)
"""
import argparse
import logging
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ConnectionException
from pymodbus.constants import DataType

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def read_registers_tcp(host: str, port: int, device_id: int, start: int, count: int, register_type: str = 'holding'):
    """Read registers from TCP Modbus device"""
    print(f"\n{'='*80}")
    print(f"Connecting to {host}:{port} (device_id: {device_id})")
    print(f"Reading {count} {register_type} registers starting at {start}")
    print(f"{'='*80}\n")
    
    client = ModbusTcpClient(host=host, port=port, timeout=3, retries=3)
    
    try:
        if not client.connect():
            print("❌ Failed to connect")
            return False
        
        print("✓ Connected successfully\n")
        
        if register_type == 'holding':
            result = client.read_holding_registers(start, count=count, device_id=device_id)
        elif register_type == 'input':
            result = client.read_input_registers(start, count=count, device_id=device_id)
        elif register_type == 'coil':
            result = client.read_coils(start, count=count, device_id=device_id)
        elif register_type == 'discrete':
            result = client.read_discrete_inputs(start, count=count, device_id=device_id)
        else:
            print(f"❌ Unknown register type: {register_type}")
            return False
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return False
        
        # Display results
        print(f"{'Register':<10} {'Dec Value':<12} {'Hex Value':<12} {'Binary':<18} {'Interpretations'}")
        print("-" * 100)
        
        if register_type in ['holding', 'input']:
            for i, value in enumerate(result.registers):
                addr = start + i
                binary = format(value, '016b')
                
                # Try different interpretations
                interpretations = []
                
                # Signed int16
                signed = value if value < 32768 else value - 65536
                if signed != value:
                    interpretations.append(f"int16: {signed}")
                
                # ASCII if printable
                if 32 <= (value >> 8) < 127 and 32 <= (value & 0xFF) < 127:
                    char1 = chr(value >> 8)
                    char2 = chr(value & 0xFF)
                    interpretations.append(f"ASCII: '{char1}{char2}'")
                
                interp_str = ", ".join(interpretations) if interpretations else "-"
                
                print(f"{addr:<10} {value:<12} 0x{value:04x}      {binary:<18} {interp_str}")
            
            # Try to interpret pairs as floats
            if len(result.registers) >= 2:
                print(f"\n{'Float Interpretations (32-bit pairs):'}")
                print("-" * 100)
                for i in range(0, len(result.registers) - 1, 2):
                    addr = start + i
                    try:
                        # Big endian
                        val_be = result.convert_from_registers(DataType.FLOAT32, i)
                        print(f"  Registers {addr}-{addr+1} (Big Endian):    {val_be:.6f}")
                    except:
                        pass
                    
                    try:
                        # Little endian
                        val_le = result.convert_from_registers(DataType.FLOAT32, i, byteorder='little')
                        print(f"  Registers {addr}-{addr+1} (Little Endian): {val_le:.6f}")
                    except:
                        pass
        
        else:  # Coils or discrete inputs
            bits = result.bits[:count]
            for i, bit in enumerate(bits):
                addr = start + i
                print(f"{addr:<10} {int(bit):<12} {'ON' if bit else 'OFF'}")
        
        return True
        
    except ConnectionException as e:
        print(f"❌ Connection error: {e}")
        return False
    except ModbusException as e:
        print(f"❌ Modbus error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()
        print(f"\n{'='*80}")
        print("Connection closed")
        print(f"{'='*80}\n")


def read_registers_rtu(port: str, baudrate: int, device_id: int, start: int, count: int, register_type: str = 'holding'):
    """Read registers from RTU Modbus device"""
    print(f"\n{'='*80}")
    print(f"Connecting to {port} at {baudrate} baud (device_id: {device_id})")
    print(f"Reading {count} {register_type} registers starting at {start}")
    print(f"{'='*80}\n")
    
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
            return False
        
        print("✓ Connected successfully\n")
        
        if register_type == 'holding':
            result = client.read_holding_registers(start, count=count, device_id=device_id)
        elif register_type == 'input':
            result = client.read_input_registers(start, count=count, device_id=device_id)
        elif register_type == 'coil':
            result = client.read_coils(start, count=count, device_id=device_id)
        elif register_type == 'discrete':
            result = client.read_discrete_inputs(start, count=count, device_id=device_id)
        else:
            print(f"❌ Unknown register type: {register_type}")
            return False
        
        if result.isError():
            print(f"❌ Error reading registers: {result}")
            return False
        
        # Display results
        print(f"{'Register':<10} {'Dec Value':<12} {'Hex Value':<12} {'Binary':<18} {'Interpretations'}")
        print("-" * 100)
        
        if register_type in ['holding', 'input']:
            for i, value in enumerate(result.registers):
                addr = start + i
                binary = format(value, '016b')
                
                # Try different interpretations
                interpretations = []
                
                # Signed int16
                signed = value if value < 32768 else value - 65536
                if signed != value:
                    interpretations.append(f"int16: {signed}")
                
                # ASCII if printable
                if 32 <= (value >> 8) < 127 and 32 <= (value & 0xFF) < 127:
                    char1 = chr(value >> 8)
                    char2 = chr(value & 0xFF)
                    interpretations.append(f"ASCII: '{char1}{char2}'")
                
                interp_str = ", ".join(interpretations) if interpretations else "-"
                
                print(f"{addr:<10} {value:<12} 0x{value:04x}      {binary:<18} {interp_str}")
            
            # Try to interpret pairs as floats
            if len(result.registers) >= 2:
                print(f"\n{'Float Interpretations (32-bit pairs):'}")
                print("-" * 100)
                for i in range(0, len(result.registers) - 1, 2):
                    addr = start + i
                    try:
                        # Big endian
                        val_be = result.convert_from_registers(DataType.FLOAT32, i)
                        print(f"  Registers {addr}-{addr+1} (Big Endian):    {val_be:.6f}")
                    except:
                        pass
                    
                    try:
                        # Little endian
                        val_le = result.convert_from_registers(DataType.FLOAT32, i, byteorder='little')
                        print(f"  Registers {addr}-{addr+1} (Little Endian): {val_le:.6f}")
                    except:
                        pass
        
        else:  # Coils or discrete inputs
            bits = result.bits[:count]
            for i, bit in enumerate(bits):
                addr = start + i
                print(f"{addr:<10} {int(bit):<12} {'ON' if bit else 'OFF'}")
        
        return True
        
    except ConnectionException as e:
        print(f"❌ Connection error: {e}")
        return False
    except ModbusException as e:
        print(f"❌ Modbus error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()
        print(f"\n{'='*80}")
        print("Connection closed")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Read Modbus Registers')
    parser.add_argument('target', type=str, help='IP address (TCP) or serial port (RTU)')
    parser.add_argument('--mode', choices=['tcp', 'rtu'], default='tcp', help='Connection mode (default: tcp)')
    parser.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('--baudrate', type=int, default=9600, help='RTU baudrate (default: 9600)')
    parser.add_argument('--device-id', type=int, default=1, help='Device/Unit ID (default: 1)')
    parser.add_argument('--start', type=int, default=0, help='Start register address (default: 0)')
    parser.add_argument('--count', type=int, default=100, help='Number of registers to read (default: 100)')
    parser.add_argument('--type', choices=['holding', 'input', 'coil', 'discrete'], 
                        default='holding', help='Register type (default: holding)')
    args = parser.parse_args()
    
    if args.mode == 'tcp':
        read_registers_tcp(args.target, args.port, args.device_id, args.start, args.count, args.type)
    else:
        read_registers_rtu(args.target, args.baudrate, args.device_id, args.start, args.count, args.type)
