"""Register parsers for Modbus data extraction using Strategy Pattern."""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Union, Optional, List
from abc import ABC, abstractmethod

# Type alias for parser return values
ParsedValue = Union[float, str, None]


class DataType(Enum):
    """Supported Modbus data types"""
    UINT16 = "uint16"           # Single 16-bit unsigned
    INT16 = "int16"             # Single 16-bit signed
    UINT32 = "uint32"           # 32-bit unsigned (2 registers)
    INT32 = "int32"             # 32-bit signed (2 registers)
    FLOAT32 = "float32"         # 32-bit float (2 registers)
    SUM = "sum"                 # Sum of multiple registers
    RAW = "raw"                 # Raw multi-register data (no parsing)
    DATETIME = "datetime"       # Date/time from 3 registers


class Endianness(Enum):
    """Byte order for multi-register values"""
    BIG = "big"
    LITTLE = "little"


@dataclass
class RegisterConfig:
    """Configuration for a single sensor"""
    address: Union[int, List[int]]
    data_type: DataType
    factor: float = 1.0
    endianness: Endianness = Endianness.BIG
    byte_swap: bool = False
    name: str = "unknown"
    offset: int = 0
    lookup: dict = None
    valid_range: Optional[tuple] = None
    
    @classmethod
    def from_dict(cls, config: dict) -> 'RegisterConfig':
        """Create from YAML config with backward compatibility"""
        addr = config.get('address')
        if addr is None:
            raise ValueError("Missing 'address' in sensor config")
        
        # Auto-detect data type if not specified (backward compatibility)
        data_type_str = config.get('data_type')
        if not data_type_str:
            if isinstance(addr, list):
                if config.get('operation') == 'sum':
                    data_type_str = 'sum'
                elif config.get('is_32bit'):
                    data_type_str = 'uint32'
                else:
                    data_type_str = 'uint16'
            else:
                # Check if factor is negative (indicates signed)
                factor = config.get('factor', 1.0)
                data_type_str = 'int16' if factor < 0 else 'uint16'
        
        valid_range = config.get('valid_range')
        if valid_range and isinstance(valid_range, list) and len(valid_range) == 2:
            valid_range = tuple(valid_range)
        
        return cls(
            address=addr,
            data_type=DataType(data_type_str),
            factor=abs(config.get('factor', 1.0)),
            endianness=Endianness(config.get('endianness', 'big')),
            byte_swap=config.get('byte_swap', False),
            name=config.get('name', 'unknown'),
            offset=config.get('offset', 0),
            lookup=config.get('lookup'),
            valid_range=valid_range
        )


class RegisterParser(ABC):
    """Base parser for register data"""
    
    @abstractmethod
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> ParsedValue:
        """Parse register value(s) into a float or string"""
        pass
    
    def _validate_addresses(self, registers: Dict[int, int], addresses: List[int]) -> bool:
        """Check all addresses exist"""
        missing = [addr for addr in addresses if addr not in registers]
        return len(missing) == 0
    
    def _apply_byte_swap(self, value: int) -> int:
        """Swap bytes within a 16-bit register"""
        return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
    
    def _validate_range(self, value: float, config: RegisterConfig) -> bool:
        """Check if value is within valid range"""
        if config.valid_range is None:
            return True
        min_val, max_val = config.valid_range
        return min_val <= value <= max_val


class UInt16Parser(RegisterParser):
    """Parse single unsigned 16-bit register"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[float]:
        addr = config.address
        if isinstance(addr, list):
            return None
            
        if addr not in registers:
            return None
        
        value = registers[addr]
        if config.byte_swap:
            value = self._apply_byte_swap(value)
        
        # Check for lookup table
        if config.lookup:
            lookup_value = config.lookup.get(value, config.lookup.get('default', f"Unknown ({value})"))
            return lookup_value
        
        # Apply offset before scaling
        if config.offset:
            value -= config.offset
        
        result = value * config.factor
        return round(result, 2)


class Int16Parser(RegisterParser):
    """Parse single signed 16-bit register"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[float]:
        addr = config.address
        if isinstance(addr, list):
            return None
            
        if addr not in registers:
            return None
        
        value = registers[addr]
        if config.byte_swap:
            value = self._apply_byte_swap(value)
        
        # Convert to signed 16-bit
        if value > 32767:
            value -= 65536
        
        # Apply offset before scaling
        if config.offset:
            value -= config.offset
        
        result = value * config.factor
        return round(result, 2)


class UInt32Parser(RegisterParser):
    """Parse 32-bit unsigned value from 2 registers"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[float]:
        if not isinstance(config.address, list):
            return None
            
        if len(config.address) != 2:
            return None
        
        if not self._validate_addresses(registers, config.address):
            return None
        
        reg_values = [registers[addr] for addr in config.address]
        if config.byte_swap:
            reg_values = [self._apply_byte_swap(v) for v in reg_values]
        
        # Combine based on endianness
        if config.endianness == Endianness.BIG:
            value = (reg_values[0] << 16) | reg_values[1]
        else:
            value = (reg_values[1] << 16) | reg_values[0]
        
        result = value * config.factor
        return round(result, 2)


class Int32Parser(RegisterParser):
    """Parse 32-bit signed value from 2 registers"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[float]:
        if not isinstance(config.address, list):
            return None
            
        if len(config.address) != 2:
            return None
        
        if not self._validate_addresses(registers, config.address):
            return None
        
        reg_values = [registers[addr] for addr in config.address]
        if config.byte_swap:
            reg_values = [self._apply_byte_swap(v) for v in reg_values]
        
        # Combine based on endianness
        if config.endianness == Endianness.BIG:
            value = (reg_values[0] << 16) | reg_values[1]
        else:
            value = (reg_values[1] << 16) | reg_values[0]
        
        # Convert to signed 32-bit
        if value > 2147483647:
            value -= 4294967296
        
        result = value * config.factor
        
        # Validate range if specified
        if not self._validate_range(result, config):
            return None
        
        return round(result, 2)


class SumParser(RegisterParser):
    """Sum multiple register values"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[float]:
        if not isinstance(config.address, list):
            return None
        
        if not self._validate_addresses(registers, config.address):
            return None
        
        reg_values = [registers[addr] for addr in config.address]
        if config.byte_swap:
            reg_values = [self._apply_byte_swap(v) for v in reg_values]
        
        total = sum(reg_values)
        result = total * config.factor
        return round(result, 2)


class RawParser(RegisterParser):
    """Parse multi-register data as text/string"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[str]:
        if not isinstance(config.address, list):
            addr = config.address
            if addr not in registers:
                return None
            # Single register as hex string
            return f"0x{registers[addr]:04X}"
        
        if not self._validate_addresses(registers, config.address):
            return None
        
        reg_values = [registers[addr] for addr in config.address]
        
        # Try to decode as ASCII text (for serial numbers, etc.)
        try:
            # Each register is 2 bytes (high byte, low byte)
            text_bytes = []
            for val in reg_values:
                high_byte = (val >> 8) & 0xFF
                low_byte = val & 0xFF
                text_bytes.extend([high_byte, low_byte])
            
            # Try to decode as ASCII, removing null bytes
            text = bytes(text_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            
            # If we got readable text, return it
            if text and text.isprintable():
                return text
        except:
            pass
        
        # Otherwise return as hex string
        hex_str = ' '.join([f"{val:04X}" for val in reg_values])
        return hex_str


class DateTimeParser(RegisterParser):
    """Parse date/time from 3 registers (Deye format)"""
    
    def parse(self, registers: Dict[int, int], config: RegisterConfig) -> Optional[str]:
        if not isinstance(config.address, list) or len(config.address) != 3:
            return None
        
        if not self._validate_addresses(registers, config.address):
            return None
        
        reg_values = [registers[addr] for addr in config.address]
        
        try:
            # Deye format (from ha-solarman): [year_month_reg, day_hour_reg, minute_second_reg]
            # Register 0: year (high byte) / month (low byte)
            # Register 1: day (high byte) / hour (low byte)
            # Register 2: minute (high byte) / second (low byte)
            year = (reg_values[0] >> 8) & 0xFF
            month = reg_values[0] & 0xFF
            day = (reg_values[1] >> 8) & 0xFF
            hour = reg_values[1] & 0xFF
            minute = (reg_values[2] >> 8) & 0xFF
            second = reg_values[2] & 0xFF
            
            # Construct full year (assuming 20xx)
            full_year = 2000 + year
            
            # Format as ISO datetime string
            datetime_str = f"{full_year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
            return datetime_str
            
        except Exception as e:
            # Fallback to hex
            hex_str = ' '.join([f"{val:04X}" for val in reg_values])
            return hex_str


class ParserFactory:
    """Factory to get the right parser for a data type"""
    
    _parsers = {
        DataType.UINT16: UInt16Parser(),
        DataType.INT16: Int16Parser(),
        DataType.UINT32: UInt32Parser(),
        DataType.INT32: Int32Parser(),
        DataType.SUM: SumParser(),
        DataType.RAW: RawParser(),
        DataType.DATETIME: DateTimeParser(),
    }
    
    @classmethod
    def get_parser(cls, data_type: DataType) -> RegisterParser:
        """Get parser instance for the given data type"""
        parser = cls._parsers.get(data_type)
        if parser is None:
            raise ValueError(f"No parser available for data type: {data_type}")
        return parser
