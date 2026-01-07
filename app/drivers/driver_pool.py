"""Connection pool for managing shared Modbus connections."""
import asyncio
from typing import Dict, Tuple, Any

driver_pool: Dict[Tuple[str, int], Any] = {}
lock = asyncio.Lock()


async def get_shared_driver(host: str, port: int, driver_class, logger):
    """Get or create a shared driver instance.
    
    Args:
        host: Host address or device path
        port: Port number (0 for serial devices)
        driver_class: Driver class to instantiate
        logger: Logger instance to pass to driver
    
    Returns:
        Driver instance
    """
    key = (host, port)
    
    async with lock:
        if key in driver_pool:
            # Reusing existing driver
            return driver_pool[key]
        
        # Creating new shared driver with logger
        driver = driver_class(logger)  # Create instance with logger
        driver_pool[key] = driver
        return driver


async def close_all_drivers():
    """Close all drivers in the pool."""
    async with lock:
        for driver in driver_pool.values():
            await driver.disconnect()
        driver_pool.clear()
