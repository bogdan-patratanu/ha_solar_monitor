"""Connection pool for sharing driver instances."""
import asyncio
import logging
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)


driver_pool: Dict[Tuple[str, int], Any] = {}
lock = asyncio.Lock()


async def get_shared_driver(host: str, port: int, driver_class):
    """Get or create a shared driver instance."""
    key = (host, port)
    
    async with lock:
        if key in driver_pool:
            logger.debug(f"Reusing existing driver for {host}:{port}")
            return driver_pool[key]
        
        logger.info(f"Creating new shared driver for {host}:{port}")
        driver = driver_class()  # Create instance of the driver class
        driver_pool[key] = driver
        return driver


async def close_all_drivers():
    """Close all drivers in the pool."""
    async with lock:
        for driver in driver_pool.values():
            await driver.disconnect()
        driver_pool.clear()
