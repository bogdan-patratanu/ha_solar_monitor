"""Pymodbus TCP driver implementation."""
import asyncio
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from .base_driver import ModbusDriver

class PyModbusTcpDriver(ModbusDriver):
    def __init__(self, logger = None):
        self.type = 'pymodbustcp'
        self.client = None
        self.lock = asyncio.Lock()
        self.logger = logger
    
    async def connect(self, path: str, host: str, port: int, timeout: int) -> bool:
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
    
    async def readRegisterValue(self, address: int, count: int, unit_id: int):
        return await self.client.read_holding_registers(
            address=address,
            count=count,
            device_id=unit_id
        )
    
    @property
    def is_connected(self) -> bool:
        return self.client and self.client.connected
