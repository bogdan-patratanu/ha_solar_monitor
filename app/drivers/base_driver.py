"""Base class for all Modbus drivers."""
import struct
from abc import ABC, abstractmethod


class ModbusDriver(ABC):
    """Abstract base class for Modbus drivers."""
    
    @abstractmethod
    async def connect(self, host: str, port: int, timeout: int) -> bool:
        """Connect to the inverter."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the inverter."""
        pass
    
    @abstractmethod
    async def readRegisterValue(self, address: int, count: int, unit_id: int):
        """Read holding registers."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
