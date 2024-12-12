# Thunder/utils/cache.py

import time
from typing import Any, Dict, Optional

from Thunder.utils.logger import logger

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_EXPIRY: int = 86400  # 24 hours

def get_cached_data(key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached data if it's not expired.
    
    Args:
        key (str): The cache key.
    
    Returns:
        Optional[Dict[str, Any]]: The cached data or None if expired/not found.
    """
    data = CACHE.get(key)
    if data and (time.time() - data['timestamp'] < CACHE_EXPIRY):
        return data
    if data:
        del CACHE[key]
    return None

def set_cache(key: str, value: Dict[str, Any]) -> None:
    """
    Set data in the cache.
    
    Args:
        key (str): The cache key.
        value (Dict[str, Any]): The data to cache.
    """
    CACHE[key] = {**value, 'timestamp': time.time()}

def clean_cache() -> None:
    """
    Remove expired entries from the cache.
    """
    current_time = time.time()
    keys_to_delete = [k for k, v in CACHE.items() if current_time - v['timestamp'] > CACHE_EXPIRY]
    for k in keys_to_delete:
        del CACHE[k]
    if keys_to_delete:
        logger.info(f"Cache cleaned up. Removed {len(keys_to_delete)} entries.")
