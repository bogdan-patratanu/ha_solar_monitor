from typing import List, Dict, Tuple, Optional
from drivers.py_modbus_tcp_driver import PyModbusTcpDriver
from drivers.umodbus_driver import UmodbusDriver
from drivers.raw_tcp_rtu_driver import RawTcpRtuDriver
from equipment import Equipment
from template_loader import TemplateLoader
import os
import json
from urllib.parse import urlparse
import logging
import sys
import re

async def load_config(config_path):
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'mqtt' not in config:
            config['mqtt'] = {}

        connections_pool = {}
        equipments = []

        if config.get('inverters'):
            await _load_equipment_from_config(
                config['inverters'],
                connections_pool,
                equipments                
            )
        
        if config.get('batteries'):
            await _load_equipment_from_config(
                config['batteries'],
                connections_pool,
                equipments
            )
        
        config['equipments'] = equipments
        config['connections_pool'] = connections_pool

        return config

    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        raise Exception(f"Error loading configuration: {e}")

async def _load_equipment_from_config(
    equipment_configs: List[Dict],
    connections_pool: Dict,
    equipments: List[Equipment]
) -> None:
    """
    Helper function to load equipment (inverters or batteries) from configuration.
    
    Args:
        equipment_configs: List of equipment configurations
        equipment_type: Type of equipment ('inverter' or 'battery')
        connections_pool: Shared connection pool
        equipments: List to append loaded equipment to
    """
    template_loader = TemplateLoader()

    for idx, eq_config in enumerate(equipment_configs):

        path = eq_config.get('path').strip()

        if not eq_config.get('name'):
            raise ValueError(f"Equipment {idx + 1}: name is required")
        if not eq_config.get('profile'):
            raise ValueError(f"Equipment {idx + 1}: profile is required")
        if not path:
            raise ValueError(f"Equipment {idx + 1}: path is required")

        if ':' in path:
            host, port = path.split(':', 1)  
            eq_config['host'] = host
            eq_config['port'] = port
        else:
            eq_config['host'] = re.sub(r"[^A-Za-z0-9]", "", path)
            eq_config['port'] = 0
        
        eq_driver = eq_config.get('driver', 'modbusRTU')
        host_port = (eq_config['host'], eq_config['port'])
        if host_port not in connections_pool:            
            eq_name = eq_config['name']
            if eq_driver == "modbusTCP":
                driver_instance = PyModbusTcpDriver()
            elif eq_driver == "modbusRTU":
                driver_instance = UmodbusDriver()
            elif eq_driver == "rawTCPRTU":
                driver_instance = RawTcpRtuDriver()
            else:
                raise ValueError(f"Unsupported driver type '{eq_driver}' for {eq_name}")
            connections_pool[host_port] = driver_instance

        template = template_loader.load_template(eq_config['profile'])
        if template is None:
            raise ValueError(f"Failed to load template for profile {eq_config['profile']}")

        equipment_configuration = template.copy()

        equipment_configuration['metadata']['name'] = eq_config.get('name')
        equipment_configuration['metadata']['ha_prefix'] = eq_config.get('ha_prefix')

        equipment_configuration['connection']['path'] = eq_config['path']
        equipment_configuration['connection']['host'] = eq_config['host']
        equipment_configuration['connection']['port'] = eq_config['port']        
        equipment_configuration['connection']['modbus_id'] = eq_config.get('modbus_id')
        equipment_configuration['connection']['driver'] = eq_driver
        equipment_configuration['connection']['driver_instance'] = connections_pool.get(host_port)

        equipment = Equipment(configuration=equipment_configuration)
        
        equipments.append(equipment)

def create_logger(log_level: str = 'INFO', name: str = 'solar_monitor'):
    """
    Create and configure a logger for the entire application.
    Uses a single logger instance compatible with Home Assistant's logging system.
    
    Args:
        log_level: Log level string (CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET)
        name: Logger name
    
    Returns:
        Configured logger instance
    """
    VALID_LOG_LEVELS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
    
    level = log_level.upper()
    if level not in VALID_LOG_LEVELS:
        level = 'INFO'
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
        force=True
    )
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    return logger