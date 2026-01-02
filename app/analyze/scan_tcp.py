import argparse
import logging
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException
from pymodbus.constants import DataType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def scan_registers(ip: str, port: int, unit_id: int, start: int, stop: int):
    """Scan registers using synchronous pymodbus"""
    logger.info(f"Connecting to {ip}:{port} (unit: {unit_id})")
    client = ModbusTcpClient(host=ip, port=port, timeout=3, retries=3)

    try:

        if not client.connect():
            raise ConnectionException("Failed to connect")
        # Read temperature (32-bit float at address 90)
        result = client.read_holding_registers(90, count=2, device_id=unit_id)
        
        if not result.isError():
            temperature = result.convert_from_registers(DataType.FLOAT32)
            logger.info(f"Temperature: {temperature:.2f}°C")
            
    except ConnectionException as e:
        logger.info(f"Connection failed: {e}")
    except ModbusException as e:
        logger.info(f"Modbus error: {e}")
    except Exception as e:
        logger.info(f"Unexpected error: {e}")
    finally:
        client.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Modbus Register Scanner')
    parser.add_argument('ip', type=str, help='IP address of the Modbus device')
    parser.add_argument('--port', type=int, default=502, help='Modbus port (default: 502)')
    parser.add_argument('--unit', type=int, default=1, help='Unit ID (default: 1)')
    parser.add_argument('--start', type=int, default=0, help='Start register address (default: 0)')
    parser.add_argument('--stop', type=int, default=500, help='Stop register address (default: 500)')
    args = parser.parse_args()

    scan_registers(args.ip, args.port, args.unit, args.start, args.stop)
