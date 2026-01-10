"""JK BMS broadcast listener driver implementation."""
import asyncio
import serial
import struct
import time
from typing import Optional, Dict, Any
from .base_driver import ModbusDriver


class JkBmsDriver(ModbusDriver):
    """Driver for JK BMS in broadcasting mode - passively listens to RS485 broadcasts."""
    
    # JK BMS proprietary protocol constants
    FRAME_HEADER_FRAME3 = bytes([0x55, 0xAA, 0xEB, 0x90, 0x02])  # Frame 3 (Live Data)
    FRAME_HEADER_FRAME1 = bytes([0x55, 0xAA, 0xEB, 0x90, 0x01])  # Frame 1 (Static)
    FRAME_HEADER_FRAME2 = bytes([0x55, 0xAA, 0xEB, 0x90, 0x03])  # Frame 2 (Setup)
    FRAME3_LENGTH = 308  # Expected frame length for Frame 3
    FRAME1_LENGTH = 308  # Expected frame length for Frame 1 (same as Frame 3)
    
    def __init__(self, logger=None):
        self.type = 'jkbms'
        self.serial_port = None
        self.connected = False
        self.logger = logger
        self._lock = asyncio.Lock()
        self._last_broadcast_data = None
        self._last_broadcast_time = 0
        self._broadcast_cache_duration = 10  # Cache broadcasts for 10 seconds
        self._serial_number = None  # BMS serial number from Trame 1
        self._bms_name = None  # BMS name from Trame 1
        self._last_frame1_time = 0  # Last time we captured Frame 1
    
    async def connect(self, path: str, host: str, port: int, timeout: int) -> bool:
        """Connect to JK BMS via serial port."""
        try:
            with open(path, 'rb'):
                pass
        except FileNotFoundError:
            self.logger.error(f"Serial device {path} does not exist")
            return False
        except PermissionError:
            self.logger.error(f"Permission denied for {path}. Try adding your user to the dialout group with: 'sudo usermod -a -G dialout $USER' and reboot")
            return False
        except Exception as e:
            self.logger.error(f"Error accessing {path}: {e}")
            return False
        
        self.logger.info(f"Connecting to JK BMS at {path} with baudrate=115200")
        try:
            self.serial_port = serial.Serial(
                port=path,
                baudrate=115200,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=timeout,
            )
            
            if self.serial_port.is_open:
                self.connected = True
                self.logger.info(f"JK BMS connected successfully on {path}")
                
                # Clear any buffered data
                await asyncio.to_thread(self.serial_port.reset_input_buffer)
                await asyncio.to_thread(self.serial_port.reset_output_buffer)
                
                return True
            return False
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from JK BMS."""
        if self.serial_port and self.serial_port.is_open:
            await asyncio.to_thread(self.serial_port.close)
            self.connected = False
            self.logger.info("JK BMS disconnected")
    
    async def readRegisterValue(self, address: int, count: int, unit_id: int):
        """
        Read data from JK BMS proprietary broadcast frames.
        
        The BMS broadcasts 308-byte frames with header 0x55 0xAA 0xEB 0x90 0x02.
        This method passively listens for these frames and extracts sensor data.
        
        Args:
            address: Starting register address (ignored - using offsets from frame)
            count: Number of registers to read (ignored - returns all available)
            unit_id: Device ID (ignored - accepts any broadcast)
        
        Returns:
            Mock Modbus response object with registers attribute
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.logger.error("JK BMS not connected")
            return None
        
        async with self._lock:
            try:
                # Check if we need to refresh Frame 1 (serial number)
                # Frame 1 is broadcast less frequently, refresh every 60 seconds
                current_time = time.time()
                if self._serial_number is None or (current_time - self._last_frame1_time) > 60:
                    self.logger.debug("Attempting to capture Frame 1 for serial number...")
                    frame1_data = await asyncio.to_thread(self._read_frame1_broadcast)
                    if frame1_data:
                        self._extract_serial_from_frame1(frame1_data)
                        self._last_frame1_time = current_time
                
                # Listen for Frame 3 broadcast frame
                self.logger.debug("Listening for JK BMS Frame 3 broadcast (308 bytes)...")
                
                # Wait and read broadcast
                broadcast_data = await asyncio.to_thread(self._read_frame3_broadcast)
                
                if not broadcast_data:
                    self.logger.warning("No Frame 3 broadcast received from JK BMS")
                    return None
                
                # Cache the broadcast data
                self._last_broadcast_data = broadcast_data
                self._last_broadcast_time = time.time()
                
                # Extract register values from Frame 3 frame
                registers = self._extract_registers_from_frame3(broadcast_data, address, count)
                
                if registers is None:
                    return None
                
                # Create mock Modbus response
                class MockResponse:
                    def __init__(self, regs):
                        self.registers = regs
                    
                    def isError(self):
                        return False
                
                return MockResponse(registers)
                
            except Exception as e:
                self.logger.error(f"Error reading JK BMS broadcast: {e}", exc_info=True)
                return None
    
    def _send_read_command(self, register: int, count: int, unit_id: int) -> None:
        """
        Send Modbus Read Holding Registers command (0x03).
        
        Frame: [SlaveID][0x03][Reg_H][Reg_L][Count_H][Count_L][CRC_L][CRC_H]
        """
        try:
            # Build command frame
            reg_high = (register >> 8) & 0xFF
            reg_low = register & 0xFF
            count_high = (count >> 8) & 0xFF
            count_low = count & 0xFF
            
            # Frame without CRC: [ID][FC][Reg_H][Reg_L][Count_H][Count_L]
            frame = bytes([
                unit_id,           # Slave ID
                0x03,              # Function code: Read Holding Registers
                reg_high,          # Register address high
                reg_low,           # Register address low
                count_high,        # Quantity high
                count_low          # Quantity low
            ])
            
            # Calculate CRC16 Modbus
            crc = self._calculate_crc16(frame)
            
            # Append CRC (little-endian)
            full_frame = frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
            
            # Clear buffers before sending
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            # Send command
            self.serial_port.write(full_frame)
            self.logger.debug(f"Sent READ command to register 0x{register:04X}, count {count}, unit {unit_id}: {full_frame.hex()}")
            
            # Wait a bit for BMS to process command
            time.sleep(0.2)
            
        except Exception as e:
            self.logger.error(f"Error sending read command: {e}")
            raise
    
    def _send_write_command(self, register: int, unit_id: int) -> None:
        """
        Send Modbus Write Multiple Registers command to trigger BMS response.
        
        Based on reference implementation:
        [SlaveID][0x10][Reg_H][Reg_L][0x00][0x01][0x02][0x00][0x00][CRC_L][CRC_H]
        """
        try:
            # Build command frame
            reg_high = (register >> 8) & 0xFF
            reg_low = register & 0xFF
            
            # Frame without CRC: [ID][FC][Reg_H][Reg_L][Qty_H][Qty_L][ByteCount][Val_H][Val_L]
            frame = bytes([
                unit_id,           # Slave ID (accept any on bus)
                0x10,              # Function code: Write Multiple Registers
                reg_high,          # Register address high
                reg_low,           # Register address low
                0x00,              # Quantity high
                0x01,              # Quantity low (1 register)
                0x02,              # Byte count
                0x00,              # Value high
                0x00               # Value low
            ])
            
            # Calculate CRC16 Modbus
            crc = self._calculate_crc16(frame)
            
            # Append CRC (little-endian)
            full_frame = frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
            
            # Clear buffers before sending
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            # Send command
            self.serial_port.write(full_frame)
            self.logger.debug(f"Sent write command to register 0x{register:04X}, unit {unit_id}: {full_frame.hex()}")
            
            # Wait a bit for BMS to process command
            time.sleep(0.2)
            
        except Exception as e:
            self.logger.error(f"Error sending write command: {e}")
            raise
    
    def _calculate_crc16(self, data: bytes) -> int:
        """
        Calculate Modbus CRC16.
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = crc >> 1
        return crc
    
    def _read_frame1_broadcast(self) -> Optional[bytes]:
        """
        Listen for JK BMS Frame 1 broadcast frames (Static data with serial number).
        
        Expected frame format:
        [0x55][0xAA][0xEB][0x90][0x01][...data 303 bytes...]
        Total length: 308 bytes
        
        Returns:
            Complete Trame 1 frame or None
        """
        try:
            # Wait for broadcast (Frame 1 is broadcast less frequently)
            max_wait_time = 15  # seconds - wait longer for Frame 1
            start_time = time.time()
            data = b''
            
            while (time.time() - start_time) < max_wait_time:
                if self.serial_port.in_waiting > 0:
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    data += chunk
                    
                    # Look for Frame 1 header in the buffer
                    if len(data) >= len(self.FRAME_HEADER_FRAME1):
                        # Search for frame header
                        for i in range(len(data) - len(self.FRAME_HEADER_FRAME1) + 1):
                            if data[i:i + len(self.FRAME_HEADER_FRAME1)] == self.FRAME_HEADER_FRAME1:
                                # Found Frame 1 header
                                self.logger.debug(f"Found Frame 1 header at offset {i}")
                                
                                # Check if we have the complete frame
                                if i + self.FRAME1_LENGTH <= len(data):
                                    frame = data[i:i + self.FRAME1_LENGTH]
                                    self.logger.info(f"Captured complete Frame 1 frame ({self.FRAME1_LENGTH} bytes)")
                                    return frame
                                else:
                                    # Need more data
                                    needed = self.FRAME1_LENGTH - (len(data) - i)
                                    self.logger.debug(f"Partial Frame 1 found, need {needed} more bytes")
                else:
                    time.sleep(0.1)  # Longer sleep for less frequent Frame 1
            
            self.logger.debug(f"Timeout waiting for Frame 1 broadcast (received {len(data)} bytes total)")
            return None
            
        except Exception as e:
            self.logger.error(f"Error listening for Frame 1 broadcast: {e}")
            return None
    
    def _read_frame3_broadcast(self) -> Optional[bytes]:
        """
        Listen for JK BMS Frame 3 broadcast frames.
        
        Expected frame format:
        [0x55][0xAA][0xEB][0x90][0x02][...data 303 bytes...]
        Total length: 308 bytes
        
        Returns:
            Complete Trame 3 frame or None
        """
        try:
            # Wait for broadcast (BMS broadcasts every ~5 seconds)
            max_wait_time = 10  # seconds
            start_time = time.time()
            data = b''
            
            while (time.time() - start_time) < max_wait_time:
                if self.serial_port.in_waiting > 0:
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    data += chunk
                    self.logger.debug(f"Received {len(chunk)} bytes, total buffer: {len(data)} bytes")
                    
                    # Look for Frame 3 header in the buffer
                    if len(data) >= len(self.FRAME_HEADER_FRAME3):
                        # Search for frame header
                        for i in range(len(data) - len(self.FRAME_HEADER_FRAME3) + 1):
                            if data[i:i + len(self.FRAME_HEADER_FRAME3)] == self.FRAME_HEADER_FRAME3:
                                # Found Frame 3 header
                                self.logger.debug(f"Found Frame 3 header at offset {i}")
                                
                                # Check if we have the complete frame
                                if i + self.FRAME3_LENGTH <= len(data):
                                    frame = data[i:i + self.FRAME3_LENGTH]
                                    self.logger.info(f"Captured complete Frame 3 frame ({self.FRAME3_LENGTH} bytes)")
                                    self.logger.debug(f"Frame header: {frame[:10].hex()}")
                                    return frame
                                else:
                                    # Need more data
                                    needed = self.FRAME3_LENGTH - (len(data) - i)
                                    self.logger.debug(f"Partial Frame 3 found, need {needed} more bytes")
                else:
                    time.sleep(0.05)  # Short sleep between checks
            
            self.logger.warning(f"Timeout waiting for Frame 3 broadcast (received {len(data)} bytes total)")
            if len(data) > 0:
                self.logger.debug(f"Buffer sample: {data[:50].hex()}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error listening for Frame 3 broadcast: {e}")
            return None
    
    def _extract_serial_from_frame1(self, frame: bytes) -> None:
        """
        Extract serial number and BMS name from Frame 1 frame.
        
        Frame 1 structure (offsets from frame start):
        - Offset 6-18: BMS Name (13 bytes ASCII)
        - Offset 46-58: Serial Number (13 bytes ASCII)
        
        Args:
            frame: Complete Frame 1 frame (308 bytes)
        """
        try:
            if len(frame) != self.FRAME1_LENGTH:
                self.logger.warning(f"Frame 1 frame wrong length: {len(frame)} bytes")
                return
            
            # Verify header
            if frame[:len(self.FRAME_HEADER_FRAME1)] != self.FRAME_HEADER_FRAME1:
                self.logger.warning("Invalid Frame 1 header")
                return
            
            # Debug: Log Frame 1 data to find correct offsets
            self.logger.info(f"Frame 1 hex dump (first 100 bytes): {frame[:100].hex()}")
            self.logger.info(f"Frame 1 offset 6-19 (BMS Name): {frame[6:19].hex()} = '{frame[6:19].decode('ascii', errors='ignore')}'")
            self.logger.info(f"Frame 1 offset 46-59 (Serial): {frame[46:59].hex()} = '{frame[46:59].decode('ascii', errors='ignore')}'")
            
            # Extract BMS name (offset 6, 13 bytes)
            bms_name_bytes = frame[6:19]
            self._bms_name = bms_name_bytes.decode('ascii', errors='ignore').strip('\x00').strip()
            
            # Extract serial number (offset 46, 13 bytes)
            serial_bytes = frame[46:59]
            self._serial_number = serial_bytes.decode('ascii', errors='ignore').strip('\x00').strip()
            
            self.logger.info(f"BMS identified - Name: '{self._bms_name}', Serial: '{self._serial_number}'")
            
        except Exception as e:
            self.logger.error(f"Error extracting serial from Frame 1: {e}", exc_info=True)
    
    def _extract_registers_from_frame3(self, frame: bytes, address: int, count: int) -> Optional[list]:
        """
        Extract register values from JK BMS Frame 3 proprietary frame.
        
        Frame format: [0x55][0xAA][0xEB][0x90][0x02][...data 303 bytes...]
        
        Data offsets (from reference documentation):
        - Offset 6-37: Cell voltages (uint16le, 2 bytes each) -> 16 cells
        - Offset 80-110: Cell resistances (int16le, 2 bytes each) -> 16 cells
        - Offset 144: MOSFET temperature (int16le)
        - Offset 154: Total power (uint32le)
        - Offset 158: Total current (int32le)
        - Offset 162-164: Temperature sensors 1-2 (int16le)
        - Offset 170: Balance current (int16le)
        - Offset 173: SOC (uint8)
        - Offset 174: Remaining capacity (int32le)
        - Offset 178: Battery capacity (int32le)
        - Offset 182: Cycle count (int32le)
        - Offset 186: Cycle capacity (int32le)
        - Offset 190: SOH (uint8)
        - Offset 194: Total runtime (uint32le)
        - Offset 198-200: Switches (uint8)
        - Offset 234: Total voltage (uint16le)
        - Offset 254, 258: Temperature sensors 3-4 (int16le)
        
        Args:
            frame: Complete Trame 3 frame (308 bytes)
            address: Starting register address to extract
            count: Number of registers to extract
        
        Returns:
            List of register values
        """
        try:
            if len(frame) != self.FRAME3_LENGTH:
                self.logger.warning(f"Frame 3 frame wrong length: {len(frame)} bytes (expected {self.FRAME3_LENGTH})")
                return None
            
            # Verify header
            if frame[:len(self.FRAME_HEADER_FRAME3)] != self.FRAME_HEADER_FRAME3:
                self.logger.warning("Invalid Frame 3 header")
                return None
            
            self.logger.debug(f"Extracting data from Frame 3 frame for registers {address} to {address + count - 1}")
            self.logger.info(f"Frame data (first 50 bytes after header): {frame[5:55].hex()}")
            
            # Map register addresses to byte offsets in Frame 3 frame
            # Base register 5664 (0x1620) corresponds to frame start (offset 0 after 5-byte header)
            # Reference doc shows data at specific byte offsets within the 303-byte payload
            
            base_register = 5664
            registers = []
            
            # Special virtual registers for serial number and BMS name
            # These are stored as ASCII strings from Trame 1, not in Trame 3
            # We'll encode them as register values for compatibility
            SERIAL_NUMBER_REG_START = 5800  # Virtual register for serial number
            BMS_NAME_REG_START = 5810  # Virtual register for BMS name
            
            # Define the offset mapping from reference documentation
            # Cell voltages start at offset 6 in the original frame (offset 1 after header)
            # But we need to map register addresses to actual data positions
            
            for i in range(count):
                reg_addr = address + i
                
                # Check if this is a virtual register for serial number or BMS name
                if reg_addr >= SERIAL_NUMBER_REG_START and reg_addr < SERIAL_NUMBER_REG_START + 7:
                    # Serial number virtual registers (7 registers = 14 chars)
                    if self._serial_number:
                        char_idx = (reg_addr - SERIAL_NUMBER_REG_START) * 2
                        serial_padded = self._serial_number.ljust(14, '\x00')
                        if char_idx < len(serial_padded):
                            # Pack 2 ASCII chars into one uint16
                            char1 = ord(serial_padded[char_idx]) if char_idx < len(serial_padded) else 0
                            char2 = ord(serial_padded[char_idx + 1]) if char_idx + 1 < len(serial_padded) else 0
                            value = (char1 << 8) | char2
                            registers.append(value)
                        else:
                            registers.append(0)
                    else:
                        registers.append(0)
                    continue
                
                if reg_addr >= BMS_NAME_REG_START and reg_addr < BMS_NAME_REG_START + 7:
                    # BMS name virtual registers (7 registers = 14 chars)
                    if self._bms_name:
                        char_idx = (reg_addr - BMS_NAME_REG_START) * 2
                        name_padded = self._bms_name.ljust(14, '\x00')
                        if char_idx < len(name_padded):
                            # Pack 2 ASCII chars into one uint16
                            char1 = ord(name_padded[char_idx]) if char_idx < len(name_padded) else 0
                            char2 = ord(name_padded[char_idx + 1]) if char_idx + 1 < len(name_padded) else 0
                            value = (char1 << 8) | char2
                            registers.append(value)
                        else:
                            registers.append(0)
                    else:
                        registers.append(0)
                    continue
                
                # Calculate byte offset in the 303-byte data section
                # Register 5664 = offset 0 in data, Register 5665 = offset 2, etc.
                byte_offset_in_data = (reg_addr - base_register) * 2
                
                # Cell 1 voltage is at offset 6 in full frame = offset 1 in data (after 5-byte header)
                # So register 5667 (cell 1) = base 5664 + 3 = offset 6 in frame
                # Register 5664 maps to frame offset 5 (right after header)
                # Register 5667 maps to frame offset 5 + (3*2) = 11... NO!
                # Actually: Register 5667 = offset 3 from base, but cell 1 is at byte 6
                # The template uses register 5667 for cell 1, which is base + 3
                # Byte offset 6 = base offset 5 + 1
                # So: (reg - 5664) * 2 gives us offset from base in bytes
                # But cell voltages start at byte 6, not byte 5
                # Register 5667 should map to byte 6: (5667-5664)*2 = 6, then +5 for header = 11
                # But cell 1 is at byte 6 total, so we need: 5 + ((5667-5664)*2 - 6) + 6 = 5 + 0 = 5? No.
                # Let me recalculate: Cell 1 at byte 6. Register 5667. 
                # If register 5664 = byte 5 (start of data), then register 5667 = byte 5 + (3*2) = byte 11
                # But cell 1 is at byte 6, not byte 11!
                # The template is wrong! Cell 1 should be at register 5664 + (6-5)/2 = 5664.5 -> 5665
                # Actually, register 5667 in template, byte 6 in frame
                # (5667 - 5664) = 3 registers = 6 bytes offset from base
                # Frame offset = 5 (header) + 6 = 11, but cell 1 is at 6
                # So the issue is: register 5667 assumes byte 11, but cell 1 is at byte 6
                # Offset adjustment needed: 6 - 11 = -5
                # OR: Cell voltages start at byte 6, which is 1 byte after header end
                # Register 5667 = base + 3, but should map to byte 6 = header(5) + 1
                # So: frame_offset = 5 + 1 + (reg_addr - 5667) * 2
                
                # Simpler approach: First cell voltage (register 5667) is at frame byte 6
                if reg_addr >= 5667:  # Cell voltages and beyond
                    frame_offset = 6 + (reg_addr - 5667) * 2
                else:  # Before cell voltages
                    frame_offset = 5 + byte_offset_in_data
                
                if frame_offset + 1 < len(frame):
                    # Read as uint16 little-endian
                    value = frame[frame_offset] | (frame[frame_offset + 1] << 8)
                    registers.append(value)
                else:
                    registers.append(0)
            
            return registers
            
        except Exception as e:
            self.logger.error(f"Error extracting registers from Frame 3: {e}", exc_info=True)
            return None
    
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected and self.serial_port and self.serial_port.is_open
