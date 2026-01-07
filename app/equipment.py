"""Generic equipment client that uses templates and supports multiple drivers."""

import asyncio
from typing import Dict, Any, Optional
import traceback
from pymodbus.exceptions import ModbusException
from drivers.driver_pool import get_shared_driver
from parsers.register_parser import RegisterConfig, ParserFactory

# Driver registry mapping
DRIVER_REGISTRY = {
    "modbusTCP": "pymodbus_driver.PymodbusDriver",
    "modbusRTU": "pymodbus_driver.PymodbusDriver"
}


class Equipment:
    """Generic equipment client that works with any manufacturer/model via templates."""
    configuration = {}
    sensors = []
    name = None
    model = None
    manufacturer = None

    def __init__(self, configuration: Dict[str, Any] = None, logger=None):
        """Initialize equipment client with template."""
        self.logger = logger

        self.configuration = configuration
        self.sensors = configuration['sensors']

        metadata = configuration.get('metadata')
        self.name = metadata['name']
        self.model = metadata['model']
        self.manufacturer = metadata['manufacturer']

        connection_config = configuration.get('connection')
        self.host = connection_config['host']
        self.port = connection_config['port']
        self.modbus_id = connection_config['modbus_id']
        self.timeout = connection_config['timeout']
        self.batch_size = connection_config['batch_size']
        driver_name = connection_config['driver']
        
        # Resolve driver class from registry
        if driver_name not in DRIVER_REGISTRY:
            raise ValueError(f"Unknown driver: {driver_name}")
        
        # Dynamically import driver class
        module_name, class_name = DRIVER_REGISTRY[driver_name].split('.')
        module = __import__(f"drivers.{module_name}", fromlist=[class_name])
        self.driver_class = getattr(module, class_name)
        
        # Initialize driver instance to None (will be set in connect method)
        self.driver_instance = None

        self.connected = False
        self.read_errors = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1.0

        self.logger.info(
            f"Initialized client for {self.name} "
            f"at {self.host}:{self.port} (Modbus ID: {self.modbus_id}, Driver: {self.driver_class.__name__}, "
            f"Sensors: {len(self.configuration.get('sensors', {}))})"
        )

    async def connect(self) -> bool:
        """Connect with slave diagnostics and initialization."""
        try:
            # First check network connectivity
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                writer.close()
                await writer.wait_closed()
                self.logger.info(f"Network connectivity to {self.host}:{self.port} confirmed")
            except Exception as e:
                self.logger.error(f"Network error connecting to {self.host}:{self.port}: {e}")
                return False
            
            # Get shared driver instance from pool
            if not self.driver_instance:
                self.driver_instance = await get_shared_driver(
                    self.host,
                    self.port,
                    self.driver_class,  # Pass the class, not the string
                    self.logger  # Pass logger to driver pool
                )
            
            # Connect the driver if not already connected
            if not hasattr(self.driver_instance, 'connected') or not self.driver_instance.connected:
                if hasattr(self.driver_instance, 'connect'):
                    success = await self.driver_instance.connect(self.host, self.port, self.timeout)
                    if not success:
                        return False
                else:
                    self.logger.error(f"Driver {type(self.driver_instance)} has no connect method")
                    return False
            
            self.connected = True
            self.logger.info(f"Connected to {self.name} using {type(self.driver_instance).__name__} driver")
            return True
        except Exception as e:
            self.connected = False
            self.logger.error(f"Connection error for {self.name}: {e}")
            return False

    async def reconnect(self) -> bool:
        """Reconnect to the equipment with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"Max reconnect attempts reached for {self.name}")
            return False

        await asyncio.sleep(self.reconnect_delay * (2 ** self.reconnect_attempts))
        self.reconnect_attempts += 1

        self.logger.info(f"Reconnecting to {self.name} (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        return await self.connect()

    async def disconnect(self):
        """Disconnect from the equipment."""
        if self.driver_instance:
            await self.driver_instance.disconnect()
            self.connected = False
            self.logger.info(f"Disconnected from {self.name}")

    async def read_data(self) -> Optional[Dict[str, Any]]:
        """Slave-aware data reading with timing."""
        self.logger.info(f"Reading data from {self.name} (ID:{self.modbus_id}) at {self.host}:{self.port}")

        if not self.connected or not self.driver_instance:
            self.logger.warning(f"Connection not active for {self.name}, attempting reconnect")
            if not await self.connect():
                self.logger.error(f"Reconnect failed for {self.name}")
                return None

        if self.modbus_id > 1:
            # Longer delay for slave devices
            await asyncio.sleep(0.7)

        # Add extra delay for slave devices
        if self.modbus_id > 1:
            await asyncio.sleep(0.2)

        try:
            # Diagnostic: Verify connectivity before read
            if not await self._verify_connectivity():
                self.logger.error(f"{self.name}: Connectivity lost before read")
                return None

            data = {}
            sensor_definitions = self.configuration.get('sensors', {})

            # Create a sorted list of unique register addresses
            all_addresses = set()
            for sensor_def in sensor_definitions.values():
                addr = sensor_def.get('address')
                if addr is None:
                    continue
                if isinstance(addr, list):
                    all_addresses.update(addr)
                else:
                    all_addresses.add(addr)
            
            if not all_addresses:
                self.logger.warning(f"{self.name}: No register addresses defined in template")
                return {}
            
            sorted_addresses = sorted(all_addresses)
            
            max_retries = 3
            retry_delay = 1.0

            # Read registers in batches to avoid gateway timeouts
            batch_size = max(1, int(self.batch_size))
            registers = {}
            attempt = 0
            
            # Process addresses in batches with strict size enforcement
            current_address = sorted_addresses[0]
            while current_address <= sorted_addresses[-1]:
                # Determine the next batch of registers to read
                batch_end = min(current_address + batch_size - 1, sorted_addresses[-1])
                count = batch_end - current_address + 1
                
                # Read this batch
                success = False
                for attempt in range(max_retries):
                    try:
                        self.logger.debug(
                            f"{self.name}: Reading {count} registers "
                            f"[{current_address} to {batch_end}] "
                            f"with slave ID {self.modbus_id}"
                        )
                        async with asyncio.timeout(self.timeout + 1):
                            result = await self.driver_instance.read_holding_registers(
                                address=current_address,
                                count=count,
                                slave=self.modbus_id
                            )

                        if result is None:
                            raise ModbusException(f"No response from device at {current_address}")

                        if hasattr(result, "isError") and result.isError():
                            raise ModbusException(f"Modbus error: {result}")

                        if not hasattr(result, "registers") or result.registers is None:
                            raise ModbusException(f"No registers in response at {current_address}")
                        
                        # Store registers in a dictionary by their address
                        for j, addr in enumerate(range(current_address, current_address + count)):
                            registers[addr] = result.registers[j]
                        
                        break  # Break out of retry loop on success

                    except (ModbusException, asyncio.TimeoutError) as e:
                        error_type = "Timeout" if isinstance(e, asyncio.TimeoutError) else "Modbus"
                        self.logger.warning(
                            f"{self.name}: {error_type} error reading registers "
                            f"[{current_address} to {batch_end}] "
                            f"(attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                        else:
                            if "GatewayNoResponse" in str(e):
                                self.logger.error(
                                    f"{self.name}: GatewayNoResponse reading registers "
                                    f"[{current_address} to {batch_end}] - "
                                    f"Check unit ID {self.modbus_id} and bridge configuration"
                                )
                            else:
                                self.logger.error(
                                    f"{self.name}: Failed after {max_retries} attempts "
                                    f"reading registers [{current_address} to {batch_end}]"
                                )
                            self.read_errors += 1
                            return None

                # On success, move to next batch
                current_address = batch_end + 1
                success = True
                
                await asyncio.sleep(0.05)  # Small pause between batches

            # Parse sensors based on template
            for sensor_id in self.configuration.get('sensors', {}):
                if sensor_id not in sensor_definitions:
                    self.logger.warning(f"{self.name}: Sensor '{sensor_id}' not found in template, skipping")
                    continue

                sensor_def = sensor_definitions[sensor_id]
                try:
                    value = self._parse_sensor_value(sensor_def, registers)
                    if value is not None:
                        data[sensor_id] = value
                except Exception as e:
                    self.logger.error(f"{self.name}: Error parsing sensor '{sensor_id}': {e}")
                    continue

            
            # Reset error count on successful read
            self.read_errors = 0
            return data

        except ModbusException as e:
            self.read_errors += 1
            
            # Special handling for slave devices
            if "slave" in self.name.lower():
                self.logger.warning(f"{self.name}: Slave device error, retrying with delay")
                await asyncio.sleep(2)  # Extra delay for slaves
                return await self.read_data()  # Retry after delay

        except asyncio.TimeoutError:
            if self.modbus_id > 1:
                self.logger.warning(f"Slave timeout for {self.name}, resetting connection")
                await self.disconnect()
                await self.connect()
                return await self.read_data()  # Retry after reset
            else:
                raise

        except (ModbusException, asyncio.TimeoutError) as e:
            if self.modbus_id > 1:
                self.logger.error(f"Slave communication error: {e}")
                self.logger.info("Resetting connection for slave")
                await self.disconnect()
                await self.connect()
                return await self.read_data()  # Retry after reset
            else:
                raise

        except Exception as e:
            self.logger.error(f"{self.name} (ID:{self.modbus_id}) communication failed: {str(e)}")
            self.logger.debug(f"Full error trace: {traceback.format_exc()}")
            self.connected = False
            return None

    async def _verify_connectivity(self) -> bool:
        """Verify network connectivity to equipment."""
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            self.logger.error(f"Network connectivity check failed for {self.name}: {e}")
            self.connected = False
            return False

    def _parse_sensor_value(self, sensor_def: Dict[str, Any], registers: Dict[int, int]) -> Optional[float]:
        """Parse a sensor value from registers using Strategy Pattern parsers."""
        try:
            config = RegisterConfig.from_dict(sensor_def)
            parser = ParserFactory.get_parser(config.data_type)
            return parser.parse(registers, config)
        except Exception as e:
            self.logger.error(f"Error parsing sensor {sensor_def.get('name', 'unknown')}: {e}")
            return None
