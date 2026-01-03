#!/usr/bin/env python3
"""
JK BMS Modbus Driver
Based on the working Home Assistant add-on implementation
Supports TCP connection via mbusd gateway
"""
import struct
import logging
from typing import Dict, Any, Optional, List
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException

logger = logging.getLogger(__name__)


class JKBMSDriver:
    """Driver for JK BMS via Modbus RTU or TCP"""
    
    # Register addresses (from Node-RED implementation)
    REG_STATIC = 0x161C      # 5660 - Static data
    REG_SETUP = 0x161E       # 5662 - Setup/configuration  
    REG_LIVE = 0x1620        # 5664 - Live/dynamic data
    REG_ALARMS = 0x12A0      # 4768 - Alarm register
    
    # Modbus function codes
    FC_READ_HOLDING = 0x03
    FC_WRITE_MULTIPLE = 0x10
    
    def __init__(self, host: str = None, port: int = 502, 
                 serial_port: str = None, baudrate: int = 9600,
                 device_id: int = 1, timeout: float = 3.0):
        """
        Initialize JK BMS driver
        
        Args:
            host: IP address for TCP connection (via mbusd gateway)
            port: TCP port (default 502)
            serial_port: Serial port for direct RTU connection
            baudrate: Serial baudrate (default 9600)
            device_id: Modbus device ID (1-15)
            timeout: Connection timeout
        """
        self.device_id = device_id
        self.timeout = timeout
        
        if host:
            self.client = ModbusTcpClient(host=host, port=port, timeout=timeout)
            self.mode = "TCP"
        elif serial_port:
            self.client = ModbusSerialClient(
                port=serial_port,
                baudrate=baudrate,
                timeout=timeout,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            self.mode = "RTU"
        else:
            raise ValueError("Either host or serial_port must be specified")
    
    def connect(self) -> bool:
        """Connect to the BMS"""
        try:
            return self.client.connect()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the BMS"""
        try:
            self.client.close()
        except Exception:
            pass
    
    def read_live_data(self) -> Optional[Dict[str, Any]]:
        """
        Read live/dynamic data from BMS (Trame 3)
        Returns dict with all sensor values
        
        JK BMS uses a special protocol: you send a Write Multiple Registers command
        to trigger the BMS, and it responds with the data in the write response.
        """
        try:
            # JK BMS protocol: Send FC 0x10 (Write Multiple Registers) to trigger data response
            # The BMS responds with a large data payload in the write response
            
            # Use write_registers to trigger the data request
            # Register 0x1620, value 0x0000
            result = self.client.write_registers(address=self.REG_LIVE, values=[0x0000], device_id=self.device_id)
            
            if result.isError():
                logger.error(f"Failed to trigger live data read: {result}")
                return None
            
            # For RTU mode, the response contains the data
            # We need to read the raw response from the transaction
            # The actual data comes back in a non-standard way
            
            # Try to read the data that was returned
            # JK BMS sends back ~300 bytes of data in response to the write
            if hasattr(result, 'registers') and result.registers:
                return self._parse_live_data(result.registers)
            
            # Alternative: The data might be in the raw response
            # For direct serial, we may need to read the buffer
            if self.mode == "RTU" and hasattr(self.client, 'framer'):
                # Try to get any pending data from the buffer
                import time
                time.sleep(0.1)  # Give BMS time to respond
                
                # Read holding registers after the write trigger
                # The BMS should have populated the registers
                read_result = self.client.read_holding_registers(address=self.REG_LIVE, count=150, device_id=self.device_id)
                
                if not read_result.isError():
                    return self._parse_live_data(read_result.registers)
            
            logger.warning("No data received from BMS")
            return None
            
        except Exception as e:
            logger.error(f"Error reading live data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_live_data(self, registers: List[int]) -> Dict[str, Any]:
        """Parse live data registers according to JK BMS protocol"""
        
        # Convert registers to bytes
        data = bytearray()
        for reg in registers:
            data.extend(struct.pack('>H', reg))  # Big-endian uint16
        
        parsed = {}
        
        try:
            # Cell voltages (16 cells) - offset 6, uint16le, scale /1000
            for i in range(16):
                offset = 6 + (i * 2)
                if offset + 1 < len(data):
                    value = struct.unpack('<H', data[offset:offset+2])[0]
                    parsed[f'cell_{i+1}_voltage'] = value / 1000.0
            
            # Cell resistances (16 cells) - offset 80, int16le, scale /1000
            for i in range(16):
                offset = 80 + (i * 2)
                if offset + 1 < len(data):
                    value = struct.unpack('<h', data[offset:offset+2])[0]
                    parsed[f'cell_{i+1}_resistance'] = value / 1000.0
            
            # MOS temperature - offset 144, int16le, scale /10
            if len(data) > 145:
                value = struct.unpack('<h', data[144:146])[0]
                parsed['mos_temperature'] = value / 10.0
            
            # Total power - offset 154, uint32le, scale /1000
            if len(data) > 157:
                value = struct.unpack('<I', data[154:158])[0]
                parsed['total_power'] = value / 1000.0
            
            # Total current - offset 158, int32le, scale /1000
            if len(data) > 161:
                value = struct.unpack('<i', data[158:162])[0]
                parsed['total_current'] = value / 1000.0
            
            # Temperature probes - int16le, scale /10
            temp_offsets = [(162, 'temp_probe_1'), (164, 'temp_probe_2'), 
                           (256, 'temp_probe_3'), (258, 'temp_probe_4')]
            for offset, name in temp_offsets:
                if len(data) > offset + 1:
                    value = struct.unpack('<h', data[offset:offset+2])[0]
                    parsed[name] = value / 10.0
            
            # Balance current - offset 170, int16le, scale /1000
            if len(data) > 171:
                value = struct.unpack('<h', data[170:172])[0]
                parsed['balance_current'] = value / 1000.0
            
            # SOC - offset 173, uint8, scale 1
            if len(data) > 173:
                parsed['soc'] = data[173]
            
            # Remaining capacity - offset 174, int32le, scale /1000
            if len(data) > 177:
                value = struct.unpack('<i', data[174:178])[0]
                parsed['remaining_capacity'] = value / 1000.0
            
            # Battery capacity - offset 178, int32le, scale /1000
            if len(data) > 181:
                value = struct.unpack('<i', data[178:182])[0]
                parsed['battery_capacity'] = value / 1000.0
            
            # Cycle count - offset 182, int32le
            if len(data) > 185:
                value = struct.unpack('<i', data[182:186])[0]
                parsed['cycle_count'] = value
            
            # Cycle capacity - offset 186, int32le, scale /1000
            if len(data) > 189:
                value = struct.unpack('<i', data[186:190])[0]
                parsed['cycle_capacity'] = value / 1000.0
            
            # SOH - offset 190, uint8
            if len(data) > 190:
                parsed['soh'] = data[190]
            
            # Total runtime - offset 194, uint32le
            if len(data) > 197:
                value = struct.unpack('<I', data[194:198])[0]
                parsed['total_runtime'] = value
            
            # Switches - offset 198-200, byte
            if len(data) > 200:
                parsed['charge_switch'] = bool(data[198])
                parsed['discharge_switch'] = bool(data[199])
                parsed['balance_switch'] = bool(data[200])
            
            # Heating - offset 215, uint8
            if len(data) > 215:
                parsed['heating'] = bool(data[215])
            
            # Total voltage - offset 234, uint16le, scale /100
            if len(data) > 235:
                value = struct.unpack('<H', data[234:236])[0]
                parsed['total_voltage'] = value / 100.0
            
            # Heating current - offset 236, int16le, scale /1000
            if len(data) > 237:
                value = struct.unpack('<h', data[236:238])[0]
                parsed['heating_current'] = value / 1000.0
            
            # Charge status - offset 278-280
            if len(data) > 280:
                parsed['charge_status_time'] = struct.unpack('<H', data[278:280])[0]
                parsed['charge_status'] = data[280]
            
            # Cell type - offset 282
            if len(data) > 282:
                parsed['cell_type'] = data[282]
            
            # Calculate derived values
            if 'total_voltage' in parsed and 'total_current' in parsed:
                parsed['calculated_power'] = parsed['total_voltage'] * parsed['total_current']
            
            # Cell statistics
            cell_voltages = [v for k, v in parsed.items() if k.startswith('cell_') and k.endswith('_voltage')]
            if cell_voltages:
                parsed['cell_voltage_max'] = max(cell_voltages)
                parsed['cell_voltage_min'] = min(cell_voltages)
                parsed['cell_voltage_avg'] = sum(cell_voltages) / len(cell_voltages)
                parsed['cell_voltage_delta'] = parsed['cell_voltage_max'] - parsed['cell_voltage_min']
            
        except Exception as e:
            logger.error(f"Error parsing live data: {e}")
        
        return parsed
    
    def read_setup_data(self) -> Optional[Dict[str, Any]]:
        """Read setup/configuration data (Trame 2)"""
        try:
            result = self.client.write_registers(self.REG_SETUP, [0x0000], device_id=self.device_id)
            if result.isError():
                return None
            
            result = self.client.read_holding_registers(self.REG_SETUP, count=150, device_id=self.device_id)
            if result.isError():
                return None
            
            return self._parse_setup_data(result.registers)
        except Exception as e:
            logger.error(f"Error reading setup data: {e}")
            return None
    
    def _parse_setup_data(self, registers: List[int]) -> Dict[str, Any]:
        """Parse setup data registers"""
        data = bytearray()
        for reg in registers:
            data.extend(struct.pack('>H', reg))
        
        parsed = {}
        
        try:
            # Key setup parameters (from Node-RED buffer-parser)
            setup_params = [
                (6, 'smart_sleep_voltage', 'int32le', 1000),
                (10, 'cell_voltage_undervoltage_protection', 'int32le', 1000),
                (14, 'cell_voltage_undervoltage_recovery', 'int32le', 1000),
                (18, 'cell_voltage_overvoltage_protection', 'int32le', 1000),
                (22, 'cell_voltage_overvoltage_recovery', 'int32le', 1000),
                (26, 'balance_trigger_voltage', 'int32le', 1000),
                (50, 'max_charge_current', 'int32le', 1000),
                (62, 'max_discharge_current', 'int32le', 1000),
                (78, 'max_balance_current', 'int32le', 1000),
                (82, 'charge_overtemperature_protection', 'int32le', 10),
                (90, 'discharge_overtemperature_protection', 'int32le', 10),
                (98, 'charge_undertemperature_protection', 'int32le', 10),
                (114, 'cell_count', 'int32le', 1),
                (130, 'total_battery_capacity', 'int32le', 1000),
                (270, 'device_address', 'int32le', 1),
            ]
            
            for offset, name, dtype, scale in setup_params:
                if len(data) > offset + 3:
                    value = struct.unpack('<i', data[offset:offset+4])[0]
                    parsed[name] = value / scale
            
        except Exception as e:
            logger.error(f"Error parsing setup data: {e}")
        
        return parsed
    
    def read_alarms(self) -> Optional[int]:
        """Read alarm register"""
        try:
            result = self.client.read_holding_registers(self.REG_ALARMS, count=2, device_id=self.device_id)
            if result.isError():
                return None
            
            # Combine 2 registers into 32-bit alarm value
            alarm_value = (result.registers[1] << 16) | result.registers[0]
            return alarm_value
        except Exception as e:
            logger.error(f"Error reading alarms: {e}")
            return None
    
    def get_all_data(self) -> Dict[str, Any]:
        """Read all data from BMS"""
        data = {
            'device_id': self.device_id,
            'mode': self.mode,
        }
        
        live = self.read_live_data()
        if live:
            data['live'] = live
        
        setup = self.read_setup_data()
        if setup:
            data['setup'] = setup
        
        alarms = self.read_alarms()
        if alarms is not None:
            data['alarms'] = alarms
        
        return data


def main():
    """Example usage"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='JK BMS Modbus Driver')
    parser.add_argument('--host', type=str, help='TCP host (mbusd gateway IP)')
    parser.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('--serial', type=str, help='Serial port for RTU')
    parser.add_argument('--baudrate', type=int, default=9600, help='Serial baudrate')
    parser.add_argument('--device-id', type=int, default=1, help='Modbus device ID (1-15)')
    parser.add_argument('--mode', choices=['live', 'setup', 'alarms', 'all'], default='all')
    
    args = parser.parse_args()
    
    # Create driver
    if args.host:
        driver = JKBMSDriver(host=args.host, port=args.port, device_id=args.device_id)
    elif args.serial:
        driver = JKBMSDriver(serial_port=args.serial, baudrate=args.baudrate, device_id=args.device_id)
    else:
        print("Error: Either --host or --serial must be specified")
        return
    
    # Connect
    if not driver.connect():
        print("Failed to connect to BMS")
        return
    
    print(f"Connected to JK BMS (device_id={args.device_id}) via {driver.mode}")
    
    try:
        if args.mode == 'live':
            data = driver.read_live_data()
        elif args.mode == 'setup':
            data = driver.read_setup_data()
        elif args.mode == 'alarms':
            data = {'alarms': driver.read_alarms()}
        else:
            data = driver.get_all_data()
        
        print(json.dumps(data, indent=2))
        
    finally:
        driver.disconnect()


if __name__ == "__main__":
    main()
