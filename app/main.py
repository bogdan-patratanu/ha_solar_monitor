import asyncio
import os
import sys
from pymodbus.exceptions import ModbusException
from equipment import Equipment
from mqtt_publisher import MQTTPublisher
from drivers.driver_pool import close_all_drivers
from common import initialize_equipments
from logger_config import create_logger


async def main_loop():
    config_path = os.getenv('CONFIG_PATH', '/data/options.json')

    try:
        # Initialize logger first with default level, will be reconfigured from config
        logger = create_logger()
        
        config, equipments = await initialize_equipments(config_path, logger)
        
        if config.get('debug', False):
            asyncio.get_event_loop().set_debug(True)

        mqtt_config = config['mqtt']

        mqtt_publisher = MQTTPublisher(
            host=mqtt_config.get('host', 'core-mosquito'),
            port=mqtt_config.get('port', 1883),
            username=mqtt_config.get('username', 'mqtt'),
            password=mqtt_config.get('password', 'mqtt'),
            discovery_prefix=mqtt_config.get('discovery_prefix', 'homeassistant'),
            logger=logger
        )

        await mqtt_publisher.connect()

        for equipment in equipments:
            await mqtt_publisher.publish_discovery(equipment)

        logger.info("Starting monitoring loop...")

        tasks = []
        for idx, inverter in enumerate(equipments):
            task = asyncio.create_task(
                monitor_equipment(inverter, mqtt_publisher, logger)
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


async def monitor_equipment(equipment: Equipment, mqtt_publisher: MQTTPublisher, logger):
    """Monitor with RS485 sharing support."""
    # Create lock per RS485 interface
    lock_key = f"{equipment.host}:{equipment.port}"
    if lock_key not in monitor_equipment.locks:
        monitor_equipment.locks[lock_key] = asyncio.Lock()
    lock = monitor_equipment.locks[lock_key]

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
            await asyncio.sleep(30)
            consecutive_errors = 0

        await asyncio.sleep(30)


# Initialize locks storage
monitor_equipment.locks = {}

if __name__ == "__main__":
    sys.exit(asyncio.run(main_loop()))
