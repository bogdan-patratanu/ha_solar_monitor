"""Deye inverter sensor definitions."""

SENSOR_DEFINITIONS = {
    'pv_voltage': {
        'address': 0,
        'name': 'PV Voltage',
        'unit': 'V',
        'factor': 0.1,
        'icon': 'mdi:flash',
        'device_class': 'voltage',
        'state_class': 'measurement'
    },
    'pv_current': {
        'address': 1,
        'name': 'PV Current',
        'unit': 'A',
        'factor': 0.1,
        'icon': 'mdi:current-dc',
        'device_class': 'current',
        'state_class': 'measurement'
    },
    'pv_power': {
        'address': 2,
        'name': 'PV Power',
        'unit': 'W',
        'factor': 1,
        'icon': 'mdi:solar-power',
        'device_class': 'power',
        'state_class': 'measurement'
    },
    'grid_voltage': {
        'address': 3,
        'name': 'Grid Voltage',
        'unit': 'V',
        'factor': 0.1,
        'icon': 'mdi:transmission-tower',
        'device_class': 'voltage',
        'state_class': 'measurement'
    },
    'grid_frequency': {
        'address': 4,
        'name': 'Grid Frequency',
        'unit': 'Hz',
        'factor': 0.01,
        'icon': 'mdi:sine-wave',
        'state_class': 'measurement'
    },
    'output_power': {
        'address': 5,
        'name': 'Output Power',
        'unit': 'W',
        'factor': 1,
        'icon': 'mdi:power-plug',
        'device_class': 'power',
        'state_class': 'measurement'
    },
    'daily_energy': {
        'address': 6,
        'name': 'Daily Energy',
        'unit': 'kWh',
        'factor': 0.1,
        'icon': 'mdi:counter',
        'device_class': 'energy',
        'state_class': 'total_increasing'
    },
    'total_energy': {
        'address': (7, 8),
        'name': 'Total Energy',
        'unit': 'kWh',
        'factor': 0.1,
        'icon': 'mdi:counter',
        'device_class': 'energy',
        'state_class': 'total_increasing',
        'is_32bit': True
    },
    'temperature': {
        'address': 9,
        'name': 'Temperature',
        'unit': '°C',
        'factor': 0.1,
        'icon': 'mdi:thermometer',
        'device_class': 'temperature',
        'state_class': 'measurement'
    }
}


def parse_sensor_value(sensor_def, registers):
    """Parse sensor value from registers based on definition."""
    if sensor_def.get('is_32bit'):
        addr_tuple = sensor_def['address']
        idx1 = addr_tuple[0]
        idx2 = addr_tuple[1]
        value = (registers[idx1] << 16 | registers[idx2]) * sensor_def['factor']
    else:
        addr = sensor_def['address']
        value = registers[addr] * sensor_def['factor']
    
    return round(value, 2)
