#!/usr/bin/env python3
"""Simple test to debug mbusd transaction ID issues."""
import asyncio
import socket
import struct
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def build_modbus_tcp_request(transaction_id, unit_id, function_code, start_address, quantity):
    """Build Modbus TCP request manually."""
    # MBAP Header: Transaction ID (2) + Protocol ID (2) + Length (2) + Unit ID (1)
    # PDU: Function Code (1) + Start Address (2) + Quantity (2)
    mbap = struct.pack('>HHHB', transaction_id, 0, 6, unit_id)
    pdu = struct.pack('>BHH', function_code, start_address, quantity)
    return mbap + pdu

def parse_modbus_tcp_response(data):
    """Parse Modbus TCP response."""
    if len(data) < 8:
        return None, "Response too short"
    
    transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', data[:8])
    
    if len(data) < 8 + length:
        return None, f"Incomplete response: expected {length+8}, got {len(data)}"
    
    function_code = data[8]
    
    if function_code & 0x80:
        # Exception response
        if length >= 2:
            exception_code = data[9]
            return {
                'transaction_id': transaction_id,
                'unit_id': unit_id,
                'function_code': function_code,
                'exception_code': exception_code,
                'is_exception': True
            }, None
        else:
            return None, "Invalid exception response"
    else:
        # Normal response
        byte_count = data[9] if length > 1 else 0
        data_bytes = data[10:10+byte_count] if byte_count > 0 else b''
        
        return {
            'transaction_id': transaction_id,
            'unit_id': unit_id,
            'function_code': function_code,
            'byte_count': byte_count,
            'data': data_bytes,
            'is_exception': False
        }, None

async def test_manual_modbus_tcp(host, port, unit_id):
    """Test Modbus TCP with manual frame construction."""
    logger.info(f"Testing manual Modbus TCP to {host}:{port}")
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        logger.info("✓ Connected successfully")
        
        # Test with different transaction IDs
        for transaction_id in [1, 0, 0x1234]:
            logger.info(f"\n--- Testing with transaction_id={transaction_id} ---")
            
            # Build request
            request = build_modbus_tcp_request(transaction_id, unit_id, 3, 0, 1)
            logger.debug(f"Sending: {request.hex()}")
            
            # Send request
            writer.write(request)
            await writer.drain()
            
            # Read response
            try:
                response = await asyncio.wait_for(reader.read(1024), timeout=3)
                logger.debug(f"Received: {response.hex()}")
                
                # Parse response
                result, error = parse_modbus_tcp_response(response)
                
                if error:
                    logger.error(f"Parse error: {error}")
                else:
                    logger.info(f"✓ Response parsed:")
                    logger.info(f"  Transaction ID: {result['transaction_id']}")
                    logger.info(f"  Unit ID: {result['unit_id']}")
                    logger.info(f"  Function Code: {result['function_code']}")
                    
                    if result['is_exception']:
                        logger.error(f"  Exception Code: {result['exception_code']}")
                    else:
                        logger.info(f"  Byte Count: {result['byte_count']}")
                        if result['data']:
                            if len(result['data']) >= 2:
                                value = struct.unpack('>H', result['data'][:2])[0]
                                logger.info(f"  Value: {value}")
                            else:
                                logger.info(f"  Data: {result['data'].hex()}")
                    
                    # Check transaction ID match
                    if result['transaction_id'] == transaction_id:
                        logger.info("✓ Transaction ID matches!")
                    else:
                        logger.warning(f"⚠ Transaction ID mismatch: expected {transaction_id}, got {result['transaction_id']}")
                
            except asyncio.TimeoutError:
                logger.error("✗ Timeout waiting for response")
                break
            except Exception as e:
                logger.error(f"✗ Read error: {e}")
                break
        
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        logger.error(f"✗ Connection error: {e}")

async def test_simple_tcp(host, port):
    """Test basic TCP connection without Modbus."""
    logger.info(f"Testing basic TCP to {host}:{port}")
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        logger.info("✓ Basic TCP connection works")
        
        # Send simple test data
        writer.write(b"TEST\n")
        await writer.drain()
        
        try:
            response = await asyncio.wait_for(reader.read(100), timeout=2)
            logger.info(f"✓ Received: {response}")
        except asyncio.TimeoutError:
            logger.info("⚠ No response to simple test (normal)")
        
        writer.close()
        await writer.wait_closed()
        return True
        
    except Exception as e:
        logger.error(f"✗ Basic TCP failed: {e}")
        return False

async def main():
    host = "192.168.123.6"
    port = 504
    unit_id = 1
    
    logger.info(f"=== Debugging mbusd transaction ID issues ===")
    
    # Test basic TCP first
    if not await test_simple_tcp(host, port):
        logger.error("Basic TCP failed - check mbusd status")
        return
    
    print("\n" + "="*50 + "\n")
    
    # Test manual Modbus TCP
    await test_manual_modbus_tcp(host, port, unit_id)
    
    print("\n" + "="*50)
    logger.info("Debug complete")

if __name__ == "__main__":
    asyncio.run(main())
