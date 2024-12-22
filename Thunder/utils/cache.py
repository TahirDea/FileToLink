import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

# Cache dictionary to store cached results
cache: Dict[str, Dict[str, Any]] = {}
CACHE_EXPIRY: int = 3600  # Cache expiry in seconds (1 hour)

def cache_function(func: Callable) -> Callable:
    """
    Decorator to cache the results of function calls for a specified duration.

    Args:
        func (Callable): The function to be cached.

    Returns:
        Callable: A wrapped function that uses caching.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        cache_key = f"{func.__name__}_{args}_{tuple(sorted(kwargs.items()))}"
        if cache_key in cache:
            cached_data = cache[cache_key]
            if time.time() - cached_data['timestamp'] < CACHE_EXPIRY:
                return cached_data['result']

        result = await func(*args, **kwargs)
        cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        return result

    return wrapper

def clean_cache():
    """Clean up expired entries from the cache."""
    current_time = time.time()
    expired_keys = [key for key, value in cache.items() if current_time - value['timestamp'] > CACHE_EXPIRY]
    for key in expired_keys:
        del cache[key]
