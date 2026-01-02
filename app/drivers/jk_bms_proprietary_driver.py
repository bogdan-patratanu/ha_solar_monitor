#!/usr/bin/env python3
"""
JK BMS Proprietary Protocol Driver
Decodes the continuous data stream from JK BMS (non-Modbus protocol)
"""
import serial
import struct
import logging
from typing import Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)


class JKBMSProprietaryDriver:
    """Driver for JK BMS proprietary protocol (continuous data stream)"""
    
    # Common JK BMS protocol markers
    FRAME_START_MARKERS = [
        b'\x4E\x57',  # 'NW' - Common JK BMS header
        b'\xAA\x55',  # Alternative header
        b'\x55\xAA',  # Alternative header
    ]
    
    def __init__(self, serial_port: str, baudrate: int = 115200, timeout: float = 1.0):
        """
        Initialize JK BMS proprietary protocol driver
        
        Args:
            serial_port: Serial port path (e.g., /dev/ttyUSB0)
            baudrate: Baudrate (default: 115200, try 9600 if this doesn't work)
            timeout: Read timeout
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.buffer = bytearray()
        
    def connect(self) -> bool:
        """Connect to the serial port"""
        try:
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            # Clear any existing data
            self.ser.reset_input_buffer()
            logger.info(f"Connected to {self.serial_port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the serial port"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Disconnected")
    
    def read_frame(self, max_attempts: int = 100) -> Optional[bytes]:
        """
        Read a complete frame from the serial port
        
        Returns:
            Complete frame data or None if no valid frame found
        """
        if not self.ser or not self.ser.is_open:
            return None
        
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            
            # Read available data
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                self.buffer.extend(data)
            
            # Look for frame start marker
            frame_start = -1
            marker_found = None
            
            for marker in self.FRAME_START_MARKERS:
                idx = self.buffer.find(marker)
                if idx >= 0:
                    frame_start = idx
                    marker_found = marker
                    break
            
            if frame_start >= 0:
                # Remove any data before the marker
                if frame_start > 0:
                    self.buffer = self.buffer[frame_start:]
                
                # Check if we have enough data for a frame
                # JK BMS frames are typically 300+ bytes
                if len(self.buffer) >= 320:
                    # Extract potential frame
                    # Frame format: [marker][length][data][checksum]
                    
                    # Try to determine frame length
                    # Common format: marker (2) + length (2) + data + checksum (varies)
                    if len(self.buffer) >= 4:
                        # Length might be at offset 2-3 (after marker)
                        potential_length = struct.unpack('>H', self.buffer[2:4])[0]
                        
                        if 10 <= potential_length <= 1024:  # Reasonable frame size
                            total_frame_size = 4 + potential_length  # marker + length + data
                            
                            if len(self.buffer) >= total_frame_size:
                                frame = bytes(self.buffer[:total_frame_size])
                                self.buffer = self.buffer[total_frame_size:]
                                return frame
                    
                    # If length parsing failed, try fixed size
                    # JK BMS typically sends ~300 byte frames
                    frame = bytes(self.buffer[:300])
                    self.buffer = self.buffer[300:]
                    return frame
            
            # Wait for more data
            if self.ser.in_waiting == 0:
                import time
                time.sleep(0.01)
        
        return None
    
    def parse_frame(self, frame: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse a JK BMS proprietary protocol frame
        
        This is a simplified parser - the actual protocol may vary by firmware version.
        You may need to adjust offsets based on your specific BMS model.
        """
        if not frame or len(frame) < 100:
            return None
        
        try:
            data = {}
            
            # Try to parse common JK BMS data points
            # Note: These offsets are estimates and may need adjustment
            
            # Cell voltages (typically 16 cells, 2 bytes each, little-endian)
            # Usually start around offset 6-10
            cell_offset = 6
            for i in range(16):
                offset = cell_offset + (i * 2)
                if offset + 1 < len(frame):
                    voltage_raw = struct.unpack('<H', frame[offset:offset+2])[0]
                    # Voltage is typically in millivolts
                    data[f'cell_{i+1}_voltage'] = voltage_raw / 1000.0
            
            # Total voltage (usually 2 bytes, scale /100)
            # Try multiple possible offsets
            for offset in [118, 150, 200]:
                if offset + 1 < len(frame):
                    total_v = struct.unpack('<H', frame[offset:offset+2])[0]
                    if 20 < total_v / 100 < 100:  # Reasonable voltage range
                        data['total_voltage'] = total_v / 100.0
                        break
            
            # Current (usually 4 bytes signed, scale /1000)
            for offset in [70, 100, 130]:
                if offset + 3 < len(frame):
                    current = struct.unpack('<i', frame[offset:offset+4])[0]
                    if -500 < current / 1000 < 500:  # Reasonable current range
                        data['total_current'] = current / 1000.0
                        break
            
            # SOC (1 byte, percentage)
            for offset in [141, 173, 200]:
                if offset < len(frame):
                    soc = frame[offset]
                    if 0 <= soc <= 100:
                        data['soc'] = soc
                        break
            
            # Temperature probes (2 bytes signed, scale /10)
            temp_offsets = [130, 132, 134, 136]
            for i, offset in enumerate(temp_offsets):
                if offset + 1 < len(frame):
                    temp = struct.unpack('<h', frame[offset:offset+2])[0]
                    if -40 < temp / 10 < 100:  # Reasonable temp range
                        data[f'temp_probe_{i+1}'] = temp / 10.0
            
            # Calculate power if we have voltage and current
            if 'total_voltage' in data and 'total_current' in data:
                data['total_power'] = data['total_voltage'] * data['total_current']
            
            # Cell statistics
            cell_voltages = [v for k, v in data.items() if k.startswith('cell_') and k.endswith('_voltage')]
            if cell_voltages:
                data['cell_voltage_max'] = max(cell_voltages)
                data['cell_voltage_min'] = min(cell_voltages)
                data['cell_voltage_avg'] = sum(cell_voltages) / len(cell_voltages)
                data['cell_voltage_delta'] = data['cell_voltage_max'] - data['cell_voltage_min']
            
            return data if data else None
            
        except Exception as e:
            logger.error(f"Error parsing frame: {e}")
            return None
    
    def read_data(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Read and parse BMS data
        
        Args:
            timeout: Maximum time to wait for valid data
        
        Returns:
            Parsed BMS data or None
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            frame = self.read_frame(max_attempts=50)
            
            if frame:
                logger.debug(f"Received frame: {len(frame)} bytes")
                logger.debug(f"Frame start: {frame[:20].hex()}")
                
                data = self.parse_frame(frame)
                if data:
                    return data
        
        logger.warning("No valid data received within timeout")
        return None


def main():
    """Test the proprietary protocol driver"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='JK BMS Proprietary Protocol Driver')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--timeout', type=float, default=5.0, help='Read timeout (default: 5s)')
    
    args = parser.parse_args()
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    driver = JKBMSProprietaryDriver(args.port, args.baudrate)
    
    if not driver.connect():
        print("Failed to connect")
        return
    
    print(f"Connected to {args.port} at {args.baudrate} baud")
    print("Reading BMS data...\n")
    
    try:
        data = driver.read_data(timeout=args.timeout)
        
        if data:
            print("✓ Data received!\n")
            print(json.dumps(data, indent=2))
        else:
            print("❌ No data received")
    
    finally:
        driver.disconnect()


if __name__ == "__main__":
    main()
