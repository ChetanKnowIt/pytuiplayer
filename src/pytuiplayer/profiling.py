"""Performance profiling utilities for pytuiplayer."""

import functools
import time
import logging

from .logging_config import get_logger

_perf_logger = get_logger("performance")


def profile(func):
    """Decorator that logs function execution time for performance profiling.
    
    Logs at DEBUG level when PYTUIP_PROFILE=1 is set, otherwise is a no-op.
    Use on critical UI event handlers to capture performance changes over time.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Fast-path skip if profiling is disabled
        import os
        if not os.getenv("PYTUIP_PROFILE"):
            return func(*args, **kwargs)
        
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            _perf_logger.debug(
                "%s: %.3fms", func.__qualname__, elapsed * 1000
            )
    return wrapper


def profile_async(func):
    """Async version of the profile decorator."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        import os
        if not os.getenv("PYTUIP_PROFILE"):
            return await func(*args, **kwargs)
        
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            _perf_logger.debug(
                "%s: %.3fms", func.__qualname__, elapsed * 1000
            )
    return wrapper
