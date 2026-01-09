import asyncio
import os
import sys
import json
import time
from pymodbus.exceptions import ModbusException
from equipment import Equipment
from mqtt_publisher import MQTTPublisher
from drivers.driver_pool import close_all_drivers
from common import load_config, create_logger


async def main_loop():
    config_path = os.getenv('CONFIG_PATH', '/data/options.json')
    logger = create_logger('INFO')

    try:
        config = await load_config(config_path)

        log_level = config.get('log_level', 'INFO')
        logger.setLevel(log_level)

        if config.get('debug', False):
            asyncio.get_event_loop().set_debug(True)
        
        equipments = config['equipments']
        inverter_count = len(config.get('inverters', []))
        battery_count = len(config.get('batteries', []))

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
        
        tasks = []
        for equipment in equipments:
            await equipment.set_logger(logger)
            await equipment.connect()
            await mqtt_publisher.publish_discovery(equipment)
            task = asyncio.create_task(
                monitor_equipment(equipment, mqtt_publisher, logger)
            )
            tasks.append(task)

        logger.info("Solar Monitor started")
        logger.info(f"Monitoring {inverter_count} inverter(s) and {battery_count} battery(ies)")
        logger.info(f"Log level: {log_level}")
        logger.info("Starting monitoring loop...")

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
        start_time = time.monotonic()
        async with lock:  # Serialize access to shared bus
            try:
                data = await equipment.read_data()
                if data:
                    try:
                        # Print data to screen instead of publishing to MQTT
                        print(f"Data for {equipment.name}:")
                        print(json.dumps(data, indent=2))
                        logger.debug(f"Printed data for {equipment.name}")
                    except Exception as e:
                        logger.error(f"Error printing data for {equipment.name}: {e}")
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
            except Exception as e:
                logger.error(f"Unexpected error reading from {equipment.name}: {e}")
                consecutive_errors += 1
        
        end_time = time.monotonic()
        duration = end_time - start_time
        logger.info(f"{equipment.name} task took {duration:.2f} seconds")
        
        if consecutive_errors >= max_consecutive_errors:
            logger.critical(
                f"{equipment.name}: {max_consecutive_errors} consecutive errors. "
                "Check equipment connection and configuration."
            )
            await asyncio.sleep(5)
            consecutive_errors = 0

        await asyncio.sleep(5)


# Initialize locks storage
monitor_equipment.locks = {}

if __name__ == "__main__":
    sys.exit(asyncio.run(main_loop()))
