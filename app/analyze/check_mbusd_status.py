#!/usr/bin/env python3
"""Check what's actually listening on port 504."""
import socket
import subprocess
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_port_listening():
    """Check what process is listening on port 504."""
    logger.info("=== Checking what's listening on port 504 ===")
    
    # Try different commands to find what's listening on port 504
    commands = [
        ['ss', '-tlnp'],
        ['lsof', '-i', ':504'],
        ['netstat', '-tlnp']
    ]
    
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if ':504' in line:
                    logger.info(f"Found with {' '.join(cmd)}: {line}")
                    
                    # Extract PID if available
                    parts = line.split()
                    process_info = None
                    
                    # Try to find PID in different positions
                    for part in parts:
                        if part.isdigit() and len(part) <= 6:  # Reasonable PID range
                            process_info = part
                            break
                        elif '/' in part and part.count('/') == 1:
                            # Format like "1234/mbusd"
                            process_info = part.split('/')[0]
                            break
                    
                    if process_info and process_info.isdigit():
                        logger.info(f"PID: {process_info}")
                        try:
                            ps_result = subprocess.run(['ps', '-p', process_info, '-o', 'pid,ppid,cmd'], capture_output=True, text=True)
                            logger.info(f"Process details:\n{ps_result.stdout}")
                        except:
                            pass
                    else:
                        logger.info(f"Process info: {parts}")
                    return True
            
            # If we get here, port wasn't found with this command
            logger.debug(f"Port 504 not found with {' '.join(cmd)}")
            
        except FileNotFoundError:
            logger.debug(f"Command {' '.join(cmd)} not found")
            continue
        except Exception as e:
            logger.debug(f"Error with {' '.join(cmd)}: {e}")
            continue
    
    logger.warning("Port 504 not found in any command output")
    logger.info("Try these manual commands:")
    logger.info("  ss -tlnp | grep 504")
    logger.info("  lsof -i :504")
    logger.info("  sudo netstat -tlnp | grep 504")
    return False

def test_raw_modbus_rtu_direct():
    """Test sending raw Modbus RTU frames directly (like referenceCode3)."""
    logger.info("\n=== Testing raw Modbus RTU frames ===")
    
    host = "192.168.123.6"
    port = 504
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        sock.connect((host, port))
        logger.info("✓ Connected to port 504")
        
        # Build raw Modbus RTU frame (like referenceCode3)
        # Unit ID: 1, Function Code: 3 (Read Holding Registers), Address: 0, Count: 1
        frame = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        
        # Add CRC16
        crc = 0x31, 0xCA  # Pre-calculated CRC for the above frame
        rtu_frame = frame + bytes(crc)
        
        logger.info(f"Sending RTU frame: {rtu_frame.hex()}")
        sock.send(rtu_frame)
        
        # Try to receive response
        try:
            response = sock.recv(1024)
            logger.info(f"Received: {response.hex()}")
            
            if len(response) >= 4:
                unit_id = response[0]
                function_code = response[1]
                byte_count = response[2] if len(response) > 2 else 0
                
                logger.info(f"Unit ID: {unit_id}")
                logger.info(f"Function Code: {function_code}")
                logger.info(f"Byte Count: {byte_count}")
                
                if function_code & 0x80:
                    exception_code = response[3] if len(response) > 3 else 0
                    logger.error(f"Exception Code: {exception_code}")
                else:
                    data = response[3:3+byte_count] if byte_count > 0 else b''
                    if len(data) >= 2:
                        value = int.from_bytes(data[:2], 'big')
                        logger.info(f"Value: {value}")
                
                return True
            else:
                logger.warning("Response too short")
                return False
                
        except socket.timeout:
            logger.error("✗ Timeout waiting for RTU response")
            return False
            
    except Exception as e:
        logger.error(f"✗ RTU test error: {e}")
        return False
    finally:
        sock.close()

def test_different_unit_ids():
    """Test different unit IDs."""
    logger.info("\n=== Testing different unit IDs ===")
    
    host = "192.168.123.6"
    port = 504
    
    for unit_id in [0, 1, 2, 3, 16, 247]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            
            sock.connect((host, port))
            
            # Simple RTU frame for different unit IDs
            frame = bytes([unit_id, 0x03, 0x00, 0x00, 0x00, 0x01])
            
            # Calculate CRC
            crc = 0xFFFF
            for byte in frame:
                crc ^= byte
                for _ in range(8):
                    if crc & 0x0001:
                        crc = (crc >> 1) ^ 0xA001
                    else:
                        crc = crc >> 1
            
            rtu_frame = frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
            
            logger.info(f"Testing unit ID {unit_id}: {rtu_frame.hex()}")
            sock.send(rtu_frame)
            
            try:
                response = sock.recv(1024)
                if len(response) > 0:
                    logger.info(f"✓ Unit ID {unit_id}: {response.hex()}")
                    
                    # Parse response
                    if len(response) >= 4 and response[0] == unit_id:
                        function_code = response[1]
                        if function_code & 0x80:
                            exception_code = response[3] if len(response) > 3 else 0
                            logger.info(f"  Exception: {exception_code}")
                        else:
                            byte_count = response[2] if len(response) > 2 else 0
                            data = response[3:3+byte_count] if byte_count > 0 else b''
                            if len(data) >= 2:
                                value = int.from_bytes(data[:2], 'big')
                                logger.info(f"  Value: {value}")
                        return unit_id  # Return the working unit ID
                    else:
                        logger.warning(f"  Unit ID mismatch: expected {unit_id}, got {response[0] if len(response) > 0 else 'none'}")
                else:
                    logger.warning(f"✗ Unit ID {unit_id}: No response")
                    
            except socket.timeout:
                logger.warning(f"✗ Unit ID {unit_id}: Timeout")
            
            sock.close()
            
        except Exception as e:
            logger.error(f"✗ Unit ID {unit_id}: Error {e}")
    
    return None

def main():
    logger.info("=== Comprehensive mbusd diagnostics ===")
    
    # Check what's listening on port 504
    if not check_port_listening():
        logger.error("Nothing is listening on port 504!")
        logger.info("Check if mbusd is running:")
        logger.info("  ps aux | grep mbusd")
        logger.info("  systemctl status mbusd")
        return
    
    print("\n" + "="*50 + "\n")
    
    # Test raw RTU frames
    if test_raw_modbus_rtu_direct():
        logger.info("✓ Raw RTU communication works!")
        
        print("\n" + "="*50 + "\n")
        
        # Test different unit IDs
        working_unit_id = test_different_unit_ids()
        if working_unit_id is not None:
            logger.info(f"✓ Working unit ID found: {working_unit_id}")
            logger.info("Update your config to use this unit ID")
        else:
            logger.warning("No working unit ID found")
    else:
        logger.error("✗ Raw RTU communication failed")
        logger.info("This suggests:")
        logger.info("1. mbusd is not configured for RTU mode")
        logger.info("2. Wrong serial port/device")
        logger.info("3. Device not responding")
        logger.info("4. Need to restart mbusd with correct configuration")

if __name__ == "__main__":
    main()
