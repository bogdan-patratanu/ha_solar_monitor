#!/usr/bin/env python3
"""Test JK BMS specific registers."""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pymodbus.client import ModbusTcpClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_jk_registers(host, port, unit_id):
    """Test JK BMS specific register addresses."""
    logger.info(f"Testing JK BMS registers on {host}:{port}")
    
    client = ModbusTcpClient(host=host, port=port, timeout=5)
    
    # JK BMS common register addresses based on templates
    jk_registers = [
        (0x0000, "System Info"),
        (0x0001, "Voltage"),
        (0x0002, "Current"), 
        (0x0003, "SOC"),
        (0x0004, "Capacity"),
        (0x0005, "Temperature"),
        (0x0100, "Cell Voltage Start"),
        (0x0110, "Cell Temperature Start"),
        (0x0200, "Alarm Status"),
        (0x0300, "BMS Status"),
        (0x0400, "Cell Count"),
        (0x1000, "Manufacturer Info"),
        (0x2000, "Serial Number"),
        (0x3000, "Firmware Version"),
        # From referenceCode3 flows
        (0x161C, 5660, "Setup Register 1"),
        (0x1620, 5664, "Setup Register 2"),
        (0x1622, 5666, "Setup Register 3"),
    ]
    
    try:
        if not client.connect():
            logger.error("Failed to connect")
            return
        
        logger.info("Connected successfully, testing registers...")
        
        successful_reads = []
        
        for reg_info in jk_registers:
            if len(reg_info) == 2:
                address, description = reg_info
                count = 1
            else:
                address, decimal, description = reg_info
                count = 1
            
            try:
                result = client.read_holding_registers(address, count=count, device_id=unit_id)
                
                if not result.isError():
                    value = result.registers[0]
                    logger.info(f"✓ {description} (0x{address:04X}): {value}")
                    successful_reads.append((address, description, value))
                else:
                    logger.warning(f"✗ {description} (0x{address:04X}): {result}")
                    
            except Exception as e:
                logger.error(f"✗ {description} (0x{address:04X}): Exception {e}")
        
        # Try reading multiple registers at once
        logger.info("\n--- Testing multi-register reads ---")
        try:
            result = client.read_holding_registers(0x0000, count=10, device_id=unit_id)
            if not result.isError():
                logger.info(f"✓ Multi-register read (0x0000-0x0009): {result.registers}")
                successful_reads.extend([(0x0000+i, f"Reg {i}", val) for i, val in enumerate(result.registers)])
            else:
                logger.warning(f"✗ Multi-register read failed: {result}")
        except Exception as e:
            logger.error(f"✗ Multi-register read exception: {e}")
        
        # Summary
        logger.info(f"\n=== SUMMARY ===")
        logger.info(f"Successful reads: {len(successful_reads)}")
        if successful_reads:
            logger.info("Working registers:")
            for addr, desc, val in successful_reads[:10]:  # Show first 10
                logger.info(f"  0x{addr:04X} ({desc}): {val}")
        
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_jk_registers("192.168.123.6", 504, 1))
