#!/usr/bin/env python3
"""Simple, robust JK BMS register test."""
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pymodbus.client import ModbusTcpClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_simple_connection(host, port, unit_id):
    """Test simple connection with delays."""
    logger.info(f"Testing simple connection to {host}:{port} (unit {unit_id})")
    
    client = ModbusTcpClient(host=host, port=port, timeout=5)
    
    try:
        if not client.connect():
            logger.error("Failed to connect")
            return False
        
        logger.info("✓ Connected successfully")
        
        # Test a few common registers with delays
        test_registers = [
            (0x0000, "System Info"),
            (0x0001, "Voltage"),
            (0x0002, "Current"),
            (0x0003, "SOC"),
            (0x0100, "Cell Voltage Start"),
            (0x0200, "Temperature Start"),
            (0x0300, "Status"),
            (0x0400, "Cell Count"),
            (0x1000, "Manufacturer"),
            (0x2000, "Serial Number"),
        ]
        
        working_regs = []
        
        for addr, name in test_registers:
            try:
                logger.info(f"Testing {name} (0x{addr:04X})...")
                
                result = client.read_holding_registers(addr, count=1, device_id=unit_id)
                
                if not result.isError():
                    value = result.registers[0]
                    logger.info(f"✓ {name}: {value}")
                    working_regs.append((addr, name, value))
                else:
                    logger.warning(f"✗ {name}: {result}")
                
                # Delay between requests
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"✗ {name}: Exception {e}")
                time.sleep(1)  # Longer delay on error
        
        if working_regs:
            logger.info(f"\n✓ Found {len(working_regs)} working registers:")
            for addr, name, value in working_regs:
                logger.info(f"  0x{addr:04X} ({name}): {value}")
            return True
        else:
            logger.warning("No working registers found")
            return False
            
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False
    finally:
        client.close()

def test_unit_ids_simple(host, port):
    """Test unit IDs with simple approach."""
    logger.info("Testing unit IDs...")
    
    for unit_id in [1, 0, 2, 16]:
        try:
            client = ModbusTcpClient(host=host, port=port, timeout=3)
            
            if client.connect():
                logger.info(f"✓ Connected with unit ID {unit_id}")
                
                # Try reading register 0
                result = client.read_holding_registers(0x0000, count=1, device_id=unit_id)
                
                if not result.isError():
                    logger.info(f"✓ Unit ID {unit_id} responds: {result.registers[0]}")
                    client.close()
                    return unit_id
                else:
                    logger.info(f"✓ Unit ID {unit_id} responds with exception: {result}")
                    client.close()
                    return unit_id  # Still responding
                
                client.close()
            else:
                logger.warning(f"✗ Failed to connect with unit ID {unit_id}")
                
        except Exception as e:
            logger.error(f"✗ Unit ID {unit_id}: {e}")
        
        time.sleep(1)
    
    return None

def main():
    host = "192.168.123.6"
    port = 504
    
    logger.info("=== Simple JK BMS Test ===")
    
    # Test unit IDs
    working_unit_id = test_unit_ids_simple(host, port)
    
    if working_unit_id is None:
        logger.warning("No unit ID responded, trying unit ID 1 anyway")
        working_unit_id = 1
    
    # Test registers
    success = test_simple_connection(host, port, working_unit_id)
    
    if success:
        logger.info("\n✓ SUCCESS! Your JK BMS is working with modbusTCP driver")
        logger.info("Update your options.json with the working unit ID if needed")
    else:
        logger.info("\n⚠ Issues found:")
        logger.info("1. Check mbusd status: systemctl status mbusd")
        logger.info("2. Check serial device: ls -la /dev/serial/by-path/")
        logger.info("3. Check JK BMS connection to serial port")
        logger.info("4. Try restarting mbusd: systemctl restart mbusd")

if __name__ == "__main__":
    main()
