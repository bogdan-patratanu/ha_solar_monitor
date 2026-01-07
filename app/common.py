from typing import List, Dict, Tuple, Optional
from drivers.pymodbus_driver import PymodbusDriver
from drivers.umodbus_driver import UmodbusDriver
from config_loader import load_config
from equipment import Equipment
from template_loader import load_equipment_template
from logger_config import create_logger


async def _load_equipment_from_config(
    equipment_configs: List[Dict],
    equipment_type: str,
    connections_pool: Dict,
    equipments: List[Equipment],
    logger
) -> None:
    """
    Helper function to load equipment (inverters or batteries) from configuration.
    
    Args:
        equipment_configs: List of equipment configurations
        equipment_type: Type of equipment ('inverter' or 'battery')
        connections_pool: Shared connection pool
        equipments: List to append loaded equipment to
    """
    for idx, eq_config in enumerate(equipment_configs):
        eq_profile = eq_config['profile']
        eq_modbus = eq_config['modbus_id']
        eq_name = eq_config['name']
        eq_path = eq_config['path']
        eq_driver = eq_config['driver']

        if eq_path is None or eq_path == "":
            logger.error(f"No connection string defined for {eq_name}")
            continue

        # Parse connection path based on driver type
        try:
            if eq_driver == "modbusTCP":
                # TCP format: "host:port" (e.g., "192.168.1.100:502")
                if ":" not in eq_path:
                    logger.error(f"Invalid TCP path format for {eq_name}: {eq_path}. Expected 'host:port'")
                    continue
                host, port_str = eq_path.rsplit(":", 1)
                port = int(port_str)
            elif eq_driver == "modbusRTU":
                # RTU format: "/dev/ttyUSB0" or "COM3" or similar serial device path
                host = eq_path  # Use the device path as the "host" identifier
                port = 0  # Port is not used for serial connections
            else:
                logger.error(f"Unknown driver type '{eq_driver}' for {eq_name}")
                continue
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid connection path format for {eq_name}: {eq_path} - {e}")
            continue

        host_port = (host, port)
        if host_port not in connections_pool:
            # Create driver instance with logger
            if eq_driver == "modbusTCP":
                driver_instance = PymodbusDriver(logger)
            elif eq_driver == "modbusRTU":
                driver_instance = UmodbusDriver(logger)
            else:
                logger.error(f"Unsupported driver type '{eq_driver}' for {eq_name}")
                continue
            connections_pool[host_port] = driver_instance

        template = load_equipment_template(eq_profile)
        if template is None:
            logger.error(f"Failed to load template for profile {eq_profile}")
            continue

        equipment_configuration = template.copy()
        equipment_configuration['metadata']['name'] = eq_name
        equipment_configuration['metadata']['ha_prefix'] = eq_config.get('ha_prefix')

        equipment_configuration['connection']['host'] = host
        equipment_configuration['connection']['port'] = port
        equipment_configuration['connection']['modbus_id'] = eq_modbus
        equipment_configuration['connection']['driver'] = eq_driver
        equipment_configuration['connection']['driver_instance'] = connections_pool[host_port]

        equipment = Equipment(configuration=equipment_configuration, logger=logger)
        await equipment.connect()
        equipments.append(equipment)
        
        logger.info(
            f"Configured {equipment_type} {idx + 1}: {equipment.name} ({equipment.model}) "
            f"at {host}:{port} with {len(equipment.sensors)} sensors"
        )


async def initialize_equipments(config_path: str, logger) -> Tuple[Dict, List[Equipment]]:
    """
    Initialize equipment from configuration.
    
    Args:
        config_path: Path to configuration file
        logger: Logger instance to use
    
    Returns:
        Tuple of (config dict, list of Equipment instances)
    """
    config = await load_config(config_path, logger)
    log_level = config.get('log_level', 'INFO')
    
    # Reconfigure logger with level from config
    logger = create_logger(log_level)

    inverter_count = len(config.get('inverters', []))
    battery_count = len(config.get('batteries', []))
    
    logger.info("Solar Monitor started")
    logger.info(f"Monitoring {inverter_count} inverter(s) and {battery_count} battery(ies)")
    logger.info(f"Log level: {log_level}")

    connections_pool = {}
    equipments = []

    if config.get('inverters'):
        await _load_equipment_from_config(
            config['inverters'],
            'inverter',
            connections_pool,
            equipments,
            logger
        )
    
    if config.get('batteries'):
        await _load_equipment_from_config(
            config['batteries'],
            'battery',
            connections_pool,
            equipments,
            logger
        )

    return config, equipments
