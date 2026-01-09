import argparse
import logging
import socket
import struct
import pymodbus.client as modbusClient
from pymodbus import ModbusException
import signal
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass


@contextmanager
def timeout_context(seconds):
    """Context manager for timeout using signals (Unix only)"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def scan_registers(ip: str, port: int, unit_id: int, timeout: float, register: int):
    """Scan registers using synchronous pymodbus TCP
    
    Args:
        ip: IP address of the Modbus device
        port: Modbus port
        unit_id: Unit ID
        timeout: Timeout in seconds
        register: Register address to read (default: 0)
    """
    logger.info(f"Connecting to {ip}:{port} (unit: {unit_id}, timeout: {timeout}s)")
    
    client = modbusClient.ModbusTcpClient(host=ip, port=port, timeout=timeout, retries=1)
    
    try:
        # Wrap both connect and read operations in a hard timeout
        with timeout_context(int(timeout * 3 + 2)):
            if not client.connect():
                raise ConnectionError("Failed to connect")
            
            logger.info(f"Connected successfully, reading register {register}...")
            
            # Try to read a single register first for detection
            result = client.read_holding_registers(register, count=1, device_id=unit_id)
            
            if result.isError():
                logger.error(f"Error response: {result}")
                return False
            
            value = result.registers[0]
            logger.info(f"✓ Register {register}: {value} (0x{value:04x})")
            return True
            
    except TimeoutError as e:
        logger.warning(f"Hard timeout: {e}")
        return False
    except ConnectionError as e:
        logger.warning(f"Connection failed: {e}")
        return False
    except ModbusException as e:
        logger.warning(f"Modbus error: {e}")
        return False
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        raise
    except Exception as e:
        logger.warning(f"Unexpected error: {e}")
        return False
    finally:
        try:
            client.close()
        except:
            pass
        logger.info("Connection closed")


def scan_full(ip: str, port: int, device_ids: list[int], timeout: float = 1.0):
    """Scan device IDs to find devices"""
    logger.info(f"Full scan of {ip}:{port}")
    logger.info(f"Testing device IDs: {device_ids}")
    
    results = []
    register_ranges = [(0, 100), (500, 600), (400, 500), (5600, 5700)]
    
    for device_id in device_ids:
        for start, stop in register_ranges:
            logger.info(f"\n--- Testing device_id: {device_id}, registers: {start}-{stop} ---")
            try:
                # Try reading from the start of each range
                if scan_registers(ip, port, device_id, timeout=timeout, register=start):
                    logger.info(f"\n✓✓✓ SUCCESS! Device found at device_id {device_id}, registers {start}-{stop} ✓✓✓\n")
                    results.append((device_id, start, stop))
            except KeyboardInterrupt:
                logger.info("\nScan interrupted by user")
                if results:
                    logger.info(f"\nFound {len(results)} device(s) before interruption:")
                    for did, s, e in results:
                        logger.info(f"  - device_id: {did}, registers: {s}-{e}")
                return results
    
    if results:
        logger.info(f"\n✓ Found {len(results)} device(s):")
        for did, s, e in results:
            logger.info(f"  - device_id: {did}, registers: {s}-{e}")
    else:
        logger.warning(f"\n✗ No devices found")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Modbus TCP Register Scanner')
    parser.add_argument('ip', type=str, help='IP address of the Modbus device')
    parser.add_argument('--port', type=int, default=502, help='Modbus port (default: 502)')
    parser.add_argument('--unit', type=int, default=1, help='Unit ID (default: 1)')
    parser.add_argument('--full-scan', action='store_true', help='Scan all device ID combinations')
    parser.add_argument('--timeout', type=float, default=1.0, help='Timeout in seconds (default: 1.0)')
    parser.add_argument('--start', type=int, default=0, help='Start register address (default: 0)')
    parser.add_argument('--stop', type=int, default=500, help='Stop register address (default: 500)')
    args = parser.parse_args()
    
    logger.info(f"Arguments: ip={args.ip}, port={args.port}, unit={args.unit}, start={args.start}, stop={args.stop}, timeout={args.timeout}, full_scan={args.full_scan}")

    common_device_ids = [0, 1, 2]

    if args.full_scan:
        scan_full(args.ip, args.port, common_device_ids, args.timeout)
    else:
        scan_registers(args.ip, args.port, args.unit, args.timeout, register=args.start)
