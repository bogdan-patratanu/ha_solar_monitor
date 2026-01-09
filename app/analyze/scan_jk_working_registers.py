#!/usr/bin/env python3
"""Scan for working JK BMS registers."""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pymodbus.client import ModbusTcpClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scan_jk_registers(host, port, unit_id):
    """Scan for valid JK BMS registers."""
    logger.info(f"Scanning JK BMS registers on {host}:{port} (unit {unit_id})")
    
    client = ModbusTcpClient(host=host, port=port, timeout=3)
    
    try:
        if not client.connect():
            logger.error("Failed to connect")
            return
        
        logger.info("Connected, scanning registers...")
        
        # Common JK BMS register ranges to test
        test_ranges = [
            (0x0000, 0x0010, "Basic Info"),
            (0x0100, 0x0120, "Cell Voltages"),
            (0x0200, 0x0210, "Cell Temperatures"), 
            (0x0300, 0x0320, "Status/Alarms"),
            (0x0400, 0x0410, "System Info"),
            (0x0500, 0x0520, "Settings"),
            (0x0600, 0x0620, "Balancing"),
            (0x0700, 0x0720, "Protection"),
            (0x0800, 0x0820, "Statistics"),
            (0x0900, 0x0920, "Manufacturer"),
            (0x1000, 0x1020, "Extended Info"),
            (0x1100, 0x1120, "Configuration"),
            (0x1200, 0x1220, "Calibration"),
            # From referenceCode3
            (0x1600, 0x1630, "Setup Registers"),
            (0x2000, 0x2020, "Serial/Version"),
        ]
        
        working_registers = []
        
        for start_addr, end_addr, description in test_ranges:
            logger.info(f"\n--- Scanning {description} (0x{start_addr:04X}-0x{end_addr:04X}) ---")
            
            # Test every 4th register to speed up scanning
            for addr in range(start_addr, end_addr + 1, 4):
                try:
                    result = client.read_holding_registers(addr, count=1, device_id=unit_id)
                    
                    if not result.isError():
                        value = result.registers[0]
                        logger.info(f"✓ 0x{addr:04X}: {value}")
                        working_registers.append((addr, value))
                        
                        # If we find a working register, test nearby ones
                        if len(working_registers) < 20:  # Limit detailed scanning
                            for offset in [-2, -1, 1, 2, 3]:
                                test_addr = addr + offset
                                if start_addr <= test_addr <= end_addr and test_addr != addr:
                                    try:
                                        result2 = client.read_holding_registers(test_addr, count=1, device_id=unit_id)
                                        if not result2.isError():
                                            value2 = result2.registers[0]
                                            logger.info(f"✓ 0x{test_addr:04X}: {value2}")
                                            working_registers.append((test_addr, value2))
                                    except:
                                        pass
                    else:
                        if result.exception_code == 4:
                            # Slave device failure - expected for non-existent registers
                            pass
                        else:
                            logger.debug(f"✗ 0x{addr:04X}: Exception {result.exception_code}")
                    
                except Exception as e:
                    logger.debug(f"✗ 0x{addr:04X}: Error {e}")
                
                # Small delay to avoid overwhelming the device
                await asyncio.sleep(0.01)
        
        # Summary
        logger.info(f"\n=== SCAN COMPLETE ===")
        logger.info(f"Found {len(working_registers)} working registers:")
        
        if working_registers:
            # Sort by address
            working_registers.sort()
            
            # Group by ranges
            ranges = []
            current_range = []
            
            for addr, value in working_registers:
                if not current_range:
                    current_range = [addr, addr]
                elif addr == current_range[1] + 4:  # Allow 4-register gaps
                    current_range[1] = addr
                else:
                    ranges.append(current_range)
                    current_range = [addr, addr]
            
            if current_range:
                ranges.append(current_range)
            
            logger.info("Register ranges found:")
            for start, end in ranges:
                logger.info(f"  0x{start:04X} - 0x{end:04X}")
            
            logger.info("\nIndividual registers:")
            for addr, value in working_registers[:20]:  # Show first 20
                logger.info(f"  0x{addr:04X}: {value}")
            
            if len(working_registers) > 20:
                logger.info(f"  ... and {len(working_registers) - 20} more")
        else:
            logger.warning("No working registers found!")
            logger.info("Try different unit IDs: 0, 1, 2, 16")
        
    except Exception as e:
        logger.error(f"Scan error: {e}")
    finally:
        client.close()

async def test_unit_ids(host, port):
    """Test different unit IDs."""
    logger.info("Testing different unit IDs...")
    
    for unit_id in [0, 1, 2, 3, 16, 247]:
        try:
            client = ModbusTcpClient(host=host, port=port, timeout=2)
            if client.connect():
                # Try a common register
                result = client.read_holding_registers(0x0000, count=1, device_id=unit_id)
                
                if not result.isError():
                    logger.info(f"✓ Unit ID {unit_id} responds!")
                    client.close()
                    return unit_id
                elif result.exception_code != 4:  # Exception 4 = slave failure (expected)
                    logger.info(f"✓ Unit ID {unit_id} responds with exception {result.exception_code}")
                    client.close()
                    return unit_id
                
                client.close()
        except:
            pass
    
    logger.warning("No unit ID responded successfully")
    return None

if __name__ == "__main__":
    host = "192.168.123.6"
    port = 504
    
    # Test different unit IDs first
    working_unit_id = asyncio.run(test_unit_ids(host, port))
    
    if working_unit_id is not None:
        logger.info(f"Using unit ID {working_unit_id}")
        asyncio.run(scan_jk_registers(host, port, working_unit_id))
    else:
        logger.info("Using default unit ID 1")
        asyncio.run(scan_jk_registers(host, port, 1))
