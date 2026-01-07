"""Base class for all Modbus drivers."""
import struct
from abc import ABC, abstractmethod


def decode_modbus_message(data: bytes, logger=None) -> str:
    """Decode Modbus TCP message into human-readable format."""
    if len(data) < 8:
        return f"Invalid Modbus message: {data.hex()}"

    # Unpack the MBAP header
    transaction_id, protocol_id, length, unit_id, function_code = struct.unpack('>HHHBB', data[:8])
    
    # Common function codes
    fc_names = {
        1: "Read Coils",
        2: "Read Discrete Inputs",
        3: "Read Holding Registers",
        4: "Read Input Registers",
        5: "Write Single Coil",
        6: "Write Single Register",
        15: "Write Multiple Coils",
        16: "Write Multiple Registers"
    }
    
    # Parse based on function code
    if function_code in [1, 2, 3, 4]:
        # Read requests
        if len(data) >= 12:
            start_addr, reg_count = struct.unpack('>HH', data[8:12])
            return (
                f"MBAP[trans:{transaction_id} proto:{protocol_id} len:{length}] "
                f"| FC:{function_code}({fc_names.get(function_code, 'Unknown')}) "
                f"| Unit:{unit_id} | Start:{start_addr} | Count:{reg_count}"
            )
    elif function_code in [5, 6]:
        # Single write requests
        if len(data) >= 12:
            address, value = struct.unpack('>HH', data[8:12])
            return (
                f"MBAP[trans:{transaction_id} proto:{protocol_id} len:{length}] "
                f"| FC:{function_code}({fc_names.get(function_code, 'Unknown')}) "
                f"| Unit:{unit_id} | Address:{address} | Value:{value}"
            )
    
    return f"MBAP[trans:{transaction_id} proto:{protocol_id} len:{length}] | FC:{function_code} | Unit:{unit_id} | Data:{data[8:].hex()}"


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
    async def read_holding_registers(self, address: int, count: int, slave: int):
        """Read holding registers."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
