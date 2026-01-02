#!/usr/bin/env python3
"""Test the RAW parser for text/string decoding."""

from parsers.register_parser import RegisterConfig, ParserFactory, DataType

# Test data - simulate serial number registers
# Example: "DEYE" encoded in registers
test_registers = {
    3: 0x4445,   # "DE"
    4: 0x5945,   # "YE"
    5: 0x3132,   # "12"
    6: 0x3334,   # "34"
    7: 0x3536,   # "56"
}

# Test serial number parsing (5 registers)
config = RegisterConfig(
    address=[3, 4, 5, 6, 7],
    data_type=DataType.RAW,
    factor=1.0,
    name="Serial Number Test"
)

parser = ParserFactory.get_parser(DataType.RAW)
result = parser.parse(test_registers, config)

print(f"Serial Number Test:")
print(f"  Registers: {[f'0x{test_registers[i]:04X}' for i in [3,4,5,6,7]]}")
print(f"  Decoded: '{result}'")
print()

# Test date/time parsing (3 registers)
datetime_registers = {
    62: 0x0714,  # Year 2020 (0x07E4) or some date encoding
    63: 0x0C1F,  # Month/Day
    64: 0x0E2A,  # Hour/Minute
}

config2 = RegisterConfig(
    address=[62, 63, 64],
    data_type=DataType.RAW,
    factor=1.0,
    name="Date Time Test"
)

result2 = parser.parse(datetime_registers, config2)
print(f"Date/Time Test:")
print(f"  Registers: {[f'0x{datetime_registers[i]:04X}' for i in [62,63,64]]}")
print(f"  Decoded: '{result2}'")
print()

# Test fault code (4 registers)
fault_registers = {
    555: 0x0000,
    556: 0x0001,
    557: 0x0000,
    558: 0x0004,
}

config3 = RegisterConfig(
    address=[555, 556, 557, 558],
    data_type=DataType.RAW,
    factor=1.0,
    name="Fault Code Test"
)

result3 = parser.parse(fault_registers, config3)
print(f"Fault Code Test:")
print(f"  Registers: {[f'0x{fault_registers[i]:04X}' for i in [555,556,557,558]]}")
print(f"  Decoded: '{result3}'")
