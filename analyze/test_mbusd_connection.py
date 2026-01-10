#!/usr/bin/env python3
"""Test script to diagnose mbusd connection issues."""
import asyncio
import socket
import struct
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pymodbus.client import ModbusTcpClient
from app.drivers.raw_tcp_rtu_driver import RawTcpRtuDriver
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_standard_modbus_tcp(host, port, unit_id):
    """Test standard Modbus TCP connection."""
    logger.info(f"Testing standard Modbus TCP to {host}:{port}")
    
    client = ModbusTcpClient(host=host, port=port, timeout=5)
    
    try:
        if client.connect():
            logger.info("✓ Standard Modbus TCP connected successfully")
            
            # Try reading a register
            result = client.read_holding_registers(0, count=1, device_id=unit_id)
            if result.isError():
                logger.error(f"✗ Modbus error: {result}")
                return False
            else:
                logger.info(f"✓ Read successful: {result.registers}")
                return True
        else:
            logger.error("✗ Failed to connect with standard Modbus TCP")
            return False
    except Exception as e:
        logger.error(f"✗ Standard Modbus TCP exception: {e}")
        return False
    finally:
        client.close()

async def test_raw_tcp_rtu(host, port, unit_id):
    """Test raw TCP RTU connection."""
    logger.info(f"Testing raw TCP RTU to {host}:{port}")
    
    driver = RawTcpRtuDriver(logger)
    
    try:
        if await driver.connect(host, port, timeout=5):
            logger.info("✓ Raw TCP RTU connected successfully")
            
            # Try reading a register
            try:
                data = await driver.readRegisterValue(0, count=1, unit_id=unit_id)
                if data and len(data) >= 2:
                    value = struct.unpack('>H', data[:2])[0]
                    logger.info(f"✓ Read successful: {value}")
                    return True
                else:
                    logger.error("✗ No data received")
                    return False
            except Exception as e:
                logger.error(f"✗ Raw TCP RTU read error: {e}")
                return False
        else:
            logger.error("✗ Failed to connect with raw TCP RTU")
            return False
    except Exception as e:
        logger.error(f"✗ Raw TCP RTU exception: {e}")
        return False
    finally:
        await driver.disconnect()

async def test_raw_socket(host, port):
    """Test basic TCP socket connection."""
    logger.info(f"Testing raw TCP socket to {host}:{port}")
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        logger.info("✓ Raw TCP socket connected successfully")
        
        # Send a simple test
        test_data = b"TEST"
        writer.write(test_data)
        await writer.drain()
        
        # Try to read response
        try:
            response = await asyncio.wait_for(reader.read(100), timeout=2)
            logger.info(f"✓ Received response: {response.hex()}")
        except asyncio.TimeoutError:
            logger.info("⚠ No response received (timeout)")
        
        writer.close()
        await writer.wait_closed()
        return True
        
    except Exception as e:
        logger.error(f"✗ Raw TCP socket error: {e}")
        return False

async def main():
    host = "192.168.123.6"
    port = 504
    unit_id = 1
    
    logger.info(f"=== Diagnosing connection to {host}:{port} ===")
    
    # Test 1: Raw TCP socket
    await test_raw_socket(host, port)
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Standard Modbus TCP
    await test_standard_modbus_tcp(host, port, unit_id)
    
    print("\n" + "="*50 + "\n")
    
    # Test 3: Raw TCP RTU
    await test_raw_tcp_rtu(host, port, unit_id)
    
    print("\n" + "="*50)
    logger.info("Diagnosis complete")

if __name__ == "__main__":
    asyncio.run(main())
