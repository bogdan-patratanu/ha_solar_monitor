import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse
from template_loader import get_template_loader
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def load_config(config_path):
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'inverters' not in config or not config['inverters']:
            raise ValueError("No inverters configured")
        
        if 'mqtt' not in config:
            config['mqtt'] = {}
        
        template_loader = get_template_loader()
        
        for idx, inv in enumerate(config['inverters']):
            if not inv.get('name'):
                raise ValueError(f"Inverter {idx + 1}: name is required")
            if not inv.get('profile'):
                raise ValueError(f"Inverter {idx + 1}: profile is required")
            if not inv.get('path'):
                raise ValueError(f"Inverter {idx + 1}: path is required")
            
            # Extract host and port from path
            parsed = urlparse(inv['path'])
            if not parsed.hostname:
                raise ValueError(f"Inverter {idx + 1}: could not parse host from path '{inv['path']}'")
            inv['host'] = parsed.hostname
            if parsed.port:
                inv['port'] = parsed.port
            
            # Determine driver based on scheme
            scheme = parsed.scheme.lower()
            if scheme == "tcp":
                inv['driver'] = "modbus_tcp"
            elif scheme in ["rtu", "serial"]:
                inv['driver'] = "modbus_rtu"
            else:
                # Default to modbus_tcp for unknown schemes
                logger.warning(f"Unknown scheme '{scheme}' for inverter {idx+1}, defaulting to modbus_tcp")
                inv['driver'] = "modbus_tcp"
            
            # Load template for this inverter using profile
            template = template_loader.load_template(inv['profile'])
            if not template:
                raise ValueError(f"Inverter {idx + 1}: Template not found for profile '{inv['profile']}'")
            
            # Store template reference
            inv['_template'] = template
            
            # Apply defaults from template
            comm_defaults = template_loader.get_communication_defaults(template)
            inv.setdefault('modbus_id', comm_defaults.get('default_modbus_id', 1))
            inv.setdefault('timeout', comm_defaults.get('default_timeout', 10))
            inv.setdefault('read_sensors_batch_size', comm_defaults.get('default_batch_size', 20))
            inv.setdefault('scan_interval', 60)
            
            # Handle sensor selection
            if 'sensors' not in inv or not inv['sensors']:
                # Check if sensor_group is specified
                sensor_group = inv.get('sensor_group')
                if sensor_group:
                    inv['sensors'] = template_loader.get_sensor_group(template, sensor_group)
                    logger.info(f"Inverter {idx + 1}: Using sensor group '{sensor_group}' with {len(inv['sensors'])} sensors")
                else:
                    # Use all sensors from template
                    inv['sensors'] = template_loader.get_all_sensors(template)
                    logger.info(f"Inverter {idx + 1}: Using all {len(inv['sensors'])} sensors from template")
            
            metadata = template_loader.get_metadata(template)
            logger.info(f"Inverter {idx + 1} ({inv['name']}): {metadata.get('manufacturer')} {metadata.get('model')} - {len(inv['sensors'])} sensors configured")
        
        logger.info(f"Configuration loaded from {config_path}")
        return config
    
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise
