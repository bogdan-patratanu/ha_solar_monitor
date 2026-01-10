import argparse
import logging
import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

# Configure logging to both console and file
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Create file handler
file_handler = logging.FileHandler('scan_rtu.log')
file_handler.setFormatter(log_formatter)

# Get root logger and configure
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

import signal
from contextlib import contextmanager
from pymodbus.constants import DataType


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


def scan_registers(port: str, baudrate: int, unit_id: int, start: int, stop: int, timeout: float = 1.0, register: int = 0):
    """Scan registers using synchronous pymodbus RTU"""
    logger.info(f"Connecting to {port} (baudrate: {baudrate}, unit: {unit_id}, timeout: {timeout}s)")
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
        retries=0,
        bytesize=8,
        parity='N',
        stopbits=1
    )

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


def scan_baudrates(port: str, unit_id: int, baudrates: list[int], timeout: float = 1.0):
    """Try multiple baudrates to find the correct one"""
    logger.info(f"Scanning {port} with unit_id={unit_id}")
    logger.info(f"Testing baudrates: {baudrates}")
    
    for baudrate in baudrates:
        logger.info(f"\n--- Testing baudrate: {baudrate} ---")
        try:
            if scan_registers(port, baudrate, unit_id, 0, 0, timeout):
                logger.info(f"\n✓✓✓ SUCCESS! Device found at baudrate {baudrate} with unit_id {unit_id} ✓✓✓\n")
                return baudrate
        except KeyboardInterrupt:
            logger.info("\nScan interrupted by user")
            return None
    
    logger.warning(f"\n✗ No response at any baudrate for unit_id={unit_id}")
    return None


def scan_full(port: str, baudrates: list[int], device_ids: list[int], timeout: float = 1.0):
    """Scan both baudrates and device IDs to find devices"""
    logger.info(f"Full scan of {port} with fixed baudrate 9600")
    logger.info(f"Testing device IDs: {device_ids}")
    
    results = []
    register_ranges = [(0, 100), (100, 200), (200, 300), (300, 400), (400, 500), (5600, 5700)]
    
    for device_id in device_ids:
        for start, stop in register_ranges:
            logger.info(f"\n--- Testing device_id: {device_id}, registers: {start}-{stop} ---")
            try:
                # Try reading from the start of each range
                if scan_registers(port, 9600, device_id, start, stop, timeout, register=start):
                    logger.info(f"\n✓✓✓ SUCCESS! Device found at device_id {device_id}, registers {start}-{stop} ✓✓✓\n")
                    results.append((9600, device_id, start, stop))
            except KeyboardInterrupt:
                logger.info("\nScan interrupted by user")
                if results:
                    logger.info(f"\nFound {len(results)} device(s) before interruption:")
                    for br, did, s, e in results:
                        logger.info(f"  - baudrate: {br}, device_id: {did}, registers: {s}-{e}")
                return results
    
    if results:
        logger.info(f"\n✓ Found {len(results)} device(s):")
        for br, did, s, e in results:
            logger.info(f"  - baudrate: {br}, device_id: {did}, registers: {s}-{e}")
    else:
        logger.warning(f"\n✗ No devices found")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Modbus RTU Register Scanner')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0 or COM3)')
    parser.add_argument('--baudrate', type=int, help='Baudrate (omit to auto-scan common rates)')
    parser.add_argument('--unit', type=int, help='Unit/Device ID (omit to auto-scan common IDs)')
    parser.add_argument('--full-scan', action='store_true', help='Scan all baudrate and device ID combinations')
    parser.add_argument('--timeout', type=float, default=1.0, help='Timeout in seconds (default: 1.0)')
    parser.add_argument('--start', type=int, default=0, help='Start register address (default: 0)')
    parser.add_argument('--stop', type=int, default=500, help='Stop register address (default: 500)')
    args = parser.parse_args()

    common_baudrates = [9600]
    common_device_ids = [0, 1, 2]

    if args.full_scan:
        # Full scan mode: try all combinations
        scan_full(args.port, common_baudrates, common_device_ids, args.timeout)
    elif args.baudrate and args.unit:
        # Single baudrate and device ID test
        scan_registers(args.port, args.baudrate, args.unit, args.start, args.stop, args.timeout)
    elif args.baudrate:
        # Fixed baudrate, scan device IDs
        logger.info(f"Scanning device IDs at baudrate {args.baudrate}")
        for device_id in common_device_ids:
            logger.info(f"\n--- Testing device_id: {device_id} ---")
            if scan_registers(args.port, args.baudrate, device_id, args.start, args.stop, args.timeout):
                logger.info(f"\n✓✓✓ SUCCESS! Device found at device_id {device_id} ✓✓✓\n")
                break
    elif args.unit:
        # Fixed device ID, scan baudrates
        scan_baudrates(args.port, args.unit, common_baudrates, args.timeout)
    else:
        # Default: scan baudrates with device_id=1
        scan_baudrates(args.port, 1, common_baudrates, args.timeout)
