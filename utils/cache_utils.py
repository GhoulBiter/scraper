"""
Utilities for managing cache
"""

import os
import shutil
from loguru import logger
from config import Config


def clear_cache():
    """Clear the request cache"""
    cache_dir = os.path.join(Config.OUTPUT_DIR, "cache")
    if os.path.exists(cache_dir):
        try:
            # Delete the entire cache directory
            shutil.rmtree(cache_dir)
            logger.success(f"Cache cleared: {cache_dir}")

            # Recreate the empty directory
            os.makedirs(cache_dir, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    else:
        logger.info("No cache to clear")
        return True
