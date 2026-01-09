"""Umodbus TCP driver implementation (placeholder)."""
from .py_modbus_tcp_driver import PyModbusTcpDriver
from .base_driver import ModbusDriver

class UmodbusDriver(ModbusDriver):
    def __init__(self, logger):
        self.type = 'umodbus'
        self.client = None
        self.connected = False
        self.logger = logger
    
    async def connect(self, host: str, port: int, timeout: int) -> bool:
        self.logger.warning("Umodbus driver not yet implemented, falling back to pymodbus")
        fallback = PyModbusTcpDriver(self.logger)
        if await fallback.connect(host, port, timeout):
            self.client = fallback.client
            self.connected = True
            return True
        return False
    
    async def disconnect(self):
        if self.client:
            self.client.close()
            self.connected = False
    
    async def readRegisterValue(self, address: int, count: int, slave: int):
        if self.client:
            return await self.client.read_holding_registers(
                address=address,
                count=count,
                slave=slave
            )
        return None
    
    @property
    def is_connected(self) -> bool:
        return self.connected
