"""Pymodbus TCP driver implementation."""
import asyncio
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from .base_driver import ModbusDriver, decode_modbus_message

class PymodbusDriver(ModbusDriver):
    def __init__(self, logger):
        self.type = 'pymodbus'
        self.client = None
        self.lock = asyncio.Lock()
        self.logger = logger
    
    async def connect(self, host: str, port: int, timeout: int) -> bool:
        try:
            self.client = AsyncModbusTcpClient(
                host=host,
                port=port,
                timeout=timeout
            )
            await self.client.connect()
            return self.client.connected
        except Exception as e:
            self.logger.error(f"Pymodbus connection error: {e}")
            return False
    
    async def disconnect(self):
        if self.client:
            self.client.close()
    
    async def read_holding_registers(self, address: int, count: int, slave: int):
        return await self.client.read_holding_registers(
            address=address,
            count=count,
        )
    
    async def _execute_request(self, request):
        """Execute request with lock and logging."""
        async with self.lock:
            try:
                # Decode and log request
                request_bytes = bytes(request)
                decoded_request = decode_modbus_message(request_bytes)
                self.logger.debug(f"Modbus request: {decoded_request}")
                
                # Send request and get response
                response = await self.client.execute(request)
                
                if response:
                    # Decode and log response
                    response_bytes = bytes(response)
                    decoded_response = decode_modbus_message(response_bytes)
                    self.logger.debug(f"Modbus response: {decoded_response}")
                
                return response
            except Exception as e:
                self.logger.error(f"Request execution error: {e}")
                return None
    
    @property
    def is_connected(self) -> bool:
        return self.client and self.client.connected
