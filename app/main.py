import asyncio
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from pymodbus.exceptions import ModbusException
from drivers.pymodbus_driver import PymodbusDriver
from drivers.umodbus_driver import UmodbusDriver
from drivers.solarman_driver import SolarmanDriver
from config_loader import load_config
from equipment import Equipment
from mqtt_publisher import MQTTPublisher
from template_loader import load_inverter_template
from drivers.driver_pool import close_all_drivers

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Suppress pymodbus internal debug logs
pymodbus_logger = logging.getLogger('pymodbus')
pymodbus_logger.setLevel(logging.WARNING)

# Enable our custom debug logging
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


async def main_loop():
    config_path = os.getenv('CONFIG_PATH', '/data/options.json')

    try:
        config = await load_config(config_path)
        log_level = config.get('log_level', 'info').upper()
        logging.getLogger().setLevel(getattr(logging, log_level))

        debug_level = config.get('debug', 0)
        asyncio.get_event_loop().set_debug(debug_level > 0)

        if debug_level > 0:
            logging.getLogger('pymodbus').setLevel(logging.DEBUG)
            logger.info("Enabled pymodbus debug logging")

        logger.info("Solar Monitor started")
        logger.info(f"Monitoring {len(config['inverters'])} inverter(s)")
        logger.info(f"Debug level: {debug_level}")
        logger.info(f"Log level: {log_level}")

        mqtt_config = config['mqtt']

        mqtt_publisher = MQTTPublisher(
            host=mqtt_config.get('host', 'core-mosquito'),
            port=mqtt_config.get('port', 1883),
            username=mqtt_config.get('username', 'mqtt'),
            password=mqtt_config.get('password', 'mqtt'),
            discovery_prefix=mqtt_config.get('discovery_prefix', 'homeassistant')
        )

        await mqtt_publisher.connect()

        # Validate slave configurations
        # slave_ids = set()
        # for inv_config in config['inverters']:
        #     modbus_id = inv_config.get('modbus_id', 1)
        #     if modbus_id > 1:
        #         if modbus_id in slave_ids:
        #             logger.error(f"Duplicate slave ID {modbus_id} detected!")
        #             sys.exit(1)
        #         slave_ids.add(modbus_id)

        #         if not inv_config.get('is_slave', False):
        #             logger.error(
        #                 f"Inverter {inv_name} has modbus_id {modbus_id} but is not marked as slave. "
        #                 "Add 'is_slave: true' to configuration."
        #             )
        #             sys.exit(1)

        #         if 'slave_delay' not in inv_config:
        #             logger.warning(
        #                 f"Slave inverter {inv_name} missing 'slave_delay' parameter. "
        #                 "Using default 0.7s"
        #             )
        #             inv_config['slave_delay'] = 0.7

        connections_pool = {}
        equipments = []
        for idx, inv_config in enumerate(config['inverters']):

            inv_profile = inv_config['profile']
            inv_modbus = inv_config['modbus_id']
            inv_name = inv_config['name']
            inv_path = inv_config['path']
            inv_driver = inv_config['driver']

            # Create driver based on protocol
            if inv_driver == "modbusTCP":
                driver_class = PymodbusDriver
            elif inv_driver == "modbusRTU":
                driver_class = UmodbusDriver
            elif inv_driver == "solarman":
                driver_class = SolarmanDriver
            else:
                logger.error(f"Unsupported protocol '{inv_driver}' for {inv_name}")
                continue

            if inv_path is None or inv_path == "":
                logger.error(f"No connection string defined for {inv_name}")
                continue

            try:
                # Parse connection string (format: protocol://host:port)
                protocol, rest = inv_path.split("://", 1)
                host, port_str = rest.rsplit(":", 1)
                port = int(port_str)

            except (ValueError, AttributeError):
                logger.error(f"Invalid connection string format for {inv_name}: {inv_path}")
                continue

            host_port = (host, port)
            if host_port not in connections_pool:
                driver_instance = driver_class()
                connections_pool[host_port] = driver_instance

            template = load_inverter_template(inv_profile)
            if template is None:
                logger.error(f"Failed to load template for profile {inv_profile}")
                continue

            inverter_configuration = template.copy()
            inverter_configuration['metadata']['name'] = inv_name
            inverter_configuration['metadata']['ha_prefix'] = inv_config.get('ha_prefix')

            inverter_configuration['connection']['host'] = host
            inverter_configuration['connection']['port'] = port
            inverter_configuration['connection']['modbus_id'] = inv_modbus
            inverter_configuration['connection']['driver'] = inv_driver
            inverter_configuration['connection']['driver_instance'] = connections_pool[host_port]

            equipment = Equipment(
                configuration=inverter_configuration
            )

            await equipment.connect()
            equipments.append(equipment)
            logger.info(
                f"Configured inverter {idx + 1}: {equipment.name} ({equipment.model}) at {host}:{port} with {len(equipment.sensors)} sensors")
            await mqtt_publisher.publish_discovery(equipment)

        logger.info("Starting monitoring loop...")

        tasks = []
        for idx, inverter in enumerate(equipments):
            task = asyncio.create_task(
                monitor_equipment(inverter, mqtt_publisher)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    except KeyboardInterrupt:
        logger.info("Shutting down")
        await close_all_drivers()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await close_all_drivers()
        return 1


async def monitor_equipment(equipment: Equipment, mqtt_publisher: MQTTPublisher):
    """Monitor with RS485 sharing support."""
    # Create lock per RS485 interface
    lock_key = f"{equipment.host}:{equipment.port}"
    if lock_key not in monitor_equipment.locks:
        monitor_equipment.locks[lock_key] = asyncio.Lock()
    lock = monitor_equipment.locks[lock_key]

    logger = logging.getLogger(__name__)
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        async with lock:  # Serialize access to shared bus
            try:
                data = await equipment.read_data()
                if data:
                    await mqtt_publisher.publish_data(equipment.name, data, equipment.manufacturer)
                    logger.debug(f"Published data for {equipment.name}")
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    logger.warning(f"No data received from {equipment.name}")
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for {equipment.name}")
                break
            except asyncio.TimeoutError:
                logger.warning(f"Timeout reading from {equipment.name}")
                consecutive_errors += 1
            except ModbusException as e:
                logger.error(f"Error reading from {equipment.name}: {e}")
                consecutive_errors += 1

        if consecutive_errors >= 5:
            logger.critical(
                f"{equipment.name}: {max_consecutive_errors} consecutive errors. "
                "Check equipment connection and configuration."
            )
            await asyncio.sleep(60)
            consecutive_errors = 0

        await asyncio.sleep(60)


# Initialize locks storage
monitor_equipment.locks = {}

if __name__ == "__main__":
    sys.exit(asyncio.run(main_loop()))
