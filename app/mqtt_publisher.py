import asyncio
import json
import logging
import paho.mqtt.client as mqtt
from equipment import Equipment

logger = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self, host, port, username=None, password=None, discovery_prefix='homeassistant'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.discovery_prefix = discovery_prefix
        self.client = mqtt.Client()

        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        logger.info(f"MQTT Publisher initialized for {host}:{port}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection. Will auto-reconnect")

    async def connect(self):
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    async def publish_discovery(self, equipment: Equipment):
        device_id = equipment.name.lower().replace(' ', '_')
        base_topic = f"{self.discovery_prefix}/sensor/{equipment.manufacturer.lower()}_{device_id}"

        # Get sensor definitions from template
        equipment_sensors = equipment.sensors

        for sensor_id in equipment_sensors:

            sensor_def = equipment_sensors[sensor_id]
            config_topic = f"{base_topic}_{sensor_id}/config"
            state_topic = f"{base_topic}/state"

            config = {
                'name': f"{equipment.name} {sensor_def.get('name', sensor_id)}",
                'unique_id': f"{equipment.manufacturer.lower()}_{device_id}_{sensor_id}",
                'state_topic': state_topic,
                'value_template': f"{{{{ value_json.{sensor_id} }}}}",
                'unit_of_measurement': sensor_def.get('unit', ''),
                'icon': sensor_def.get('icon', 'mdi:gauge'),
                'device': {
                    'identifiers': [f"{equipment.manufacturer.lower()}_{device_id}"],
                    'name': equipment.name,
                    'manufacturer': equipment.manufacturer,
                    'model': equipment.model,
                    'sw_version': '1.0.0',
                },
                'availability_topic': f"{base_topic}/availability",
                'payload_available': 'online',
                'payload_not_available': 'offline'
            }

            # Add device_class and state_class from template
            if 'device_class' in sensor_def:
                config['device_class'] = sensor_def['device_class']
            if 'state_class' in sensor_def:
                config['state_class'] = sensor_def['state_class']

            self.client.publish(config_topic, json.dumps(config), retain=True)

        await asyncio.sleep(0.1)
        logger.info(f"Published discovery configuration for {equipment.name}")

    async def publish_data(self, equipment_name, data, manufacturer='Unknown'):
        device_id = equipment_name.lower().replace(' ', '_')
        base_topic = f"{self.discovery_prefix}/sensor/{manufacturer.lower()}_{device_id}"
        state_topic = f"{base_topic}/state"
        availability_topic = f"{base_topic}/availability"

        self.client.publish(availability_topic, "online", retain=True)
        self.client.publish(state_topic, json.dumps(data))

    async def publish_offline(self, equipment_name, manufacturer='Unknown'):
        """Publish offline status for an equipment."""
        device_id = equipment_name.lower().replace(' ', '_')
        base_topic = f"{self.discovery_prefix}/sensor/{manufacturer.lower()}_{device_id}"
        availability_topic = f"{base_topic}/availability"

        self.client.publish(availability_topic, "offline", retain=True)
        logger.warning(f"Published offline status for {equipment_name}")
