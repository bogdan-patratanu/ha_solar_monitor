"""Pymodbus RTU driver implementation."""
from pymodbus.client import ModbusSerialClient
import asyncio
from .base_driver import ModbusDriver

class PyModbusRtuDriver(ModbusDriver):
    def __init__(self, logger = None):
        self.type = 'pymodbusrtu'
        self.client = None
        self.connected = False
        self.logger = logger
    
    async def connect(self, path: str, host: str, port: int, timeout: int) -> bool:
        # Check if device exists
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
            
        self.logger.info(f"Connecting to RTU device at {path} with baudrate=115200")
        try:
            self.client = ModbusSerialClient(
                port=path,
                baudrate=115200,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=timeout,
                handle_local_echo=False,
            )
            # Run connect in a thread
            connected = await asyncio.to_thread(self.client.connect)
            if connected:
                self.connected = True
                return True
            return False
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        if self.client:
            self.client.close()
            self.connected = False
    
    async def readRegisterValue(self, address: int, count: int, unit_id: int):
        if self.client:
            # Run the synchronous Modbus call in a thread
            return await asyncio.to_thread(
                self.client.read_holding_registers,
                address=address,
                count=count,
                device_id=unit_id
            )
        return None
    
    @property
    def is_connected(self) -> bool:
        return self.connected
