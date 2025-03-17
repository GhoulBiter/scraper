"""
Session management with caching capabilities
"""

import os
from aiohttp_client_cache import CachedSession, SQLiteBackend
from loguru import logger
from config import Config


async def create_cached_session():
    """
    Create a cached aiohttp session that stores responses in SQLite.

    Returns:
        CachedSession: An aiohttp session with caching capabilities
    """
    # Create cache directory if it doesn't exist
    cache_dir = os.path.join(Config.OUTPUT_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    # Define the cache backend
    cache_db = os.path.join(cache_dir, "crawler_cache.sqlite")

    # Configure the cache backend with optimal settings
    cache_backend = SQLiteBackend(
        cache_name=cache_db,
        expire_after=86400,  # Cache for 1 day (24 hours)
        allowed_methods=("GET",),  # Only cache GET requests
        timeout=60,  # Generous timeout for university websites
        # Don't cache error responses
        ignored_params=["random", "utm_source", "utm_medium", "utm_campaign"],
        # Exclude common analytics and tracking parameters from cache key
    )

    logger.info(f"Initializing cached session with database: {cache_db}")

    # Create the cached session
    session = CachedSession(
        cache=cache_backend,
        headers={
            "User-Agent": Config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "DNT": "1",
        },
    )

    # Return the session
    return session


async def close_cached_session(session):
    """
    Close the cached session properly.

    Args:
        session: The cached session to close
    """
    if session:
        try:
            await session.close()
            # Optional: explicitly close the cache connection
            if hasattr(session, "cache") and hasattr(session.cache, "close"):
                await session.cache.close()
            logger.info("Cached session closed")
        except Exception as e:
            logger.error(f"Error closing cached session: {e}")
