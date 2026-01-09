"""Raw TCP Modbus RTU driver implementation similar to .referenceCode3."""
import asyncio
import socket
import struct
from .base_driver import ModbusDriver


def crc16(data: bytes) -> int:
    """Calculate CRC16 for Modbus RTU frame."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc


def build_modbus_rtu_frame(unit_id: int, function_code: int, data: bytes) -> bytes:
    """Build Modbus RTU frame with CRC."""
    frame = bytes([unit_id, function_code]) + data
    crc = crc16(frame)
    return frame + struct.pack('<H', crc)


def parse_modbus_rtu_response(frame: bytes) -> tuple:
    """Parse Modbus RTU response frame."""
    if len(frame) < 4:
        raise ValueError("Frame too short")
    
    unit_id = frame[0]
    function_code = frame[1]
    
    # Check for exception response
    if function_code & 0x80:
        if len(frame) >= 5:
            exception_code = frame[2]
            return unit_id, function_code, exception_code, None
        raise ValueError("Invalid exception response")
    
    # Normal response
    data = frame[2:-2]  # Exclude unit_id, function_code, and CRC
    return unit_id, function_code, None, data


class RawTcpRtuDriver(ModbusDriver):
    """Raw TCP driver that sends Modbus RTU frames over TCP socket."""
    
    def __init__(self, logger):
        self.type = 'raw_tcp_rtu'
        self.reader = None
        self.writer = None
        self.lock = asyncio.Lock()
        self.logger = logger
        self._host = None
        self._port = None
    
    async def connect(self, host: str, port: int, timeout: int) -> bool:
        """Connect to TCP gateway."""
        try:
            self._host = host
            self._port = port
            
            # Create TCP connection
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            
            self.logger.info(f"Connected to {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"TCP connection error: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Close TCP connection."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
            finally:
                self.writer = None
                self.reader = None
                self.logger.info("TCP connection closed")
    
    async def readRegisterValue(self, address: int, count: int, unit_id: int):
        """Read holding registers using Modbus RTU over TCP."""
        return await self._execute_modbus_request(
            unit_id=unit_id,
            function_code=3,  # Read Holding Registers
            data=struct.pack('>HH', address, count)
        )
    
    async def write_single_register(self, address: int, value: int, unit_id: int):
        """Write single register using Modbus RTU over TCP."""
        return await self._execute_modbus_request(
            unit_id=unit_id,
            function_code=6,  # Write Single Register
            data=struct.pack('>HH', address, value)
        )
    
    async def write_multiple_registers(self, address: int, values: list[int], unit_id: int):
        """Write multiple registers using Modbus RTU over TCP."""
        data = struct.pack('>HH', address, len(values))
        data += bytes([len(values) * 2])  # Byte count
        for value in values:
            data += struct.pack('>H', value)
        
        return await self._execute_modbus_request(
            unit_id=unit_id,
            function_code=16,  # Write Multiple Registers
            data=data
        )
    
    async def _execute_modbus_request(self, unit_id: int, function_code: int, data: bytes):
        """Execute Modbus RTU request over TCP with lock and logging."""
        async with self.lock:
            try:
                if not self.writer or not self.reader:
                    raise ConnectionError("Not connected")
                
                # Build RTU frame
                frame = build_modbus_rtu_frame(unit_id, function_code, data)
                
                # Log request
                self.logger.debug(f"Sending RTU frame: {frame.hex()}")
                
                # Send frame
                self.writer.write(frame)
                await self.writer.drain()
                
                # Read response (with timeout)
                response = await asyncio.wait_for(
                    self._read_frame(), 
                    timeout=5.0
                )
                
                # Log response
                self.logger.debug(f"Received RTU frame: {response.hex()}")
                
                # Parse response
                resp_unit_id, resp_function_code, exception_code, resp_data = parse_modbus_rtu_response(response)
                
                # Check for exceptions
                if exception_code is not None:
                    raise Exception(f"Modbus exception {exception_code}")
                
                # Validate response
                if resp_unit_id != unit_id:
                    raise ValueError(f"Unit ID mismatch: expected {unit_id}, got {resp_unit_id}")
                
                if resp_function_code != function_code:
                    raise ValueError(f"Function code mismatch: expected {function_code}, got {resp_function_code}")
                
                return resp_data
                
            except Exception as e:
                self.logger.error(f"Modbus request error: {e}")
                raise
    
    async def _read_frame(self) -> bytes:
        """Read complete Modbus RTU frame from TCP socket."""
        buffer = bytearray()
        
        try:
            # Read unit ID and function code
            header = await self.reader.readexactly(2)
            buffer.extend(header)
            
            # Determine expected frame length based on function code
            function_code = buffer[1]
            
            if function_code & 0x80:
                # Exception response: unit_id + function_code + exception_code + CRC
                remaining = await self.reader.readexactly(3)
                buffer.extend(remaining)
            else:
                # Normal response - need to parse to determine length
                if function_code in [1, 2, 3, 4]:
                    # Read response: unit_id + function_code + byte_count + data + CRC
                    byte_count_byte = await self.reader.readexactly(1)
                    buffer.extend(byte_count_byte)
                    byte_count = byte_count_byte[0]
                    
                    # Read data bytes
                    if byte_count > 0:
                        data_bytes = await self.reader.readexactly(byte_count)
                        buffer.extend(data_bytes)
                    
                    # Read CRC (2 bytes)
                    crc_bytes = await self.reader.readexactly(2)
                    buffer.extend(crc_bytes)
                    
                elif function_code in [5, 6, 15, 16]:
                    # Write responses: unit_id + function_code + address + quantity/value + CRC
                    remaining = await self.reader.readexactly(4)
                    buffer.extend(remaining)
                    
                    # Read CRC (2 bytes)
                    crc_bytes = await self.reader.readexactly(2)
                    buffer.extend(crc_bytes)
                else:
                    raise ValueError(f"Unsupported function code: {function_code}")
            
            return bytes(buffer)
            
        except asyncio.IncompleteReadError:
            raise ConnectionError("Connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.writer is not None and not self.writer.is_closing()
    
    def get_connection_info(self) -> dict:
        """Get connection information."""
        return {
            'type': self.type,
            'host': self._host,
            'port': self._port,
            'connected': self.is_connected
        }
