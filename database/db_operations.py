"""
Core database operations for the crawler
"""

import os
import asyncio
import aiosqlite
from loguru import logger

from config import Config

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "crawler_data.db")

# Global connection pool (for reuse)
_connection = None
_connection_lock = asyncio.Lock()


async def get_connection():
    """Get a database connection (reusing existing if available)."""
    global _connection

    if _connection is None:
        async with _connection_lock:
            if _connection is None:
                try:
                    _connection = await aiosqlite.connect(DB_PATH)
                    # Enable foreign keys
                    await _connection.execute("PRAGMA foreign_keys = ON")
                    # For better performance
                    await _connection.execute("PRAGMA journal_mode = WAL")
                except Exception as e:
                    logger.error(f"Error connecting to database: {e}")
                    raise

    return _connection


async def close_connection():
    """Close the database connection."""
    global _connection

    if _connection is not None:
        async with _connection_lock:
            if _connection is not None:
                try:
                    await _connection.close()
                    _connection = None
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")


async def init_database():
    """Initialize the database schema."""
    if not Config.USE_SQLITE:
        logger.info("SQLite database is disabled in config.")
        return

    try:
        conn = await get_connection()

        # Create tables
        await conn.execute(
            """
        CREATE TABLE IF NOT EXISTS crawl_runs (
            run_id TEXT PRIMARY KEY,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            university TEXT,
            total_urls_visited INTEGER DEFAULT 0,
            total_application_pages INTEGER DEFAULT 0,
            total_actual_applications INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
        """
        )

        await conn.execute(
            """
        CREATE TABLE IF NOT EXISTS api_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            pages_evaluated INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0.0,
            FOREIGN KEY (run_id) REFERENCES crawl_runs(run_id)
        )
        """
        )

        await conn.execute(
            """
        CREATE TABLE IF NOT EXISTS application_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            university TEXT,
            depth INTEGER,
            is_actual_application INTEGER DEFAULT 0,
            ai_evaluation TEXT,
            found_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES crawl_runs(run_id)
        )
        """
        )

        # Create indexes for better performance
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_pages_run_id ON application_pages(run_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_metrics_run_id ON api_metrics(run_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_pages_url ON application_pages(url)"
        )

        await conn.commit()
        logger.success("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def start_crawl_run(run_id, university):
    """Record the start of a crawl run."""
    if not Config.USE_SQLITE:
        return

    try:
        conn = await get_connection()
        await conn.execute(
            "INSERT INTO crawl_runs (run_id, university) VALUES (?, ?)",
            (run_id, university),
        )
        await conn.commit()
        logger.info(f"Recorded start of crawl run {run_id}")
    except Exception as e:
        logger.error(f"Failed to record crawl run start: {e}")


async def end_crawl_run(run_id, total_urls_visited, total_app_pages, total_actual_apps):
    """Record the end of a crawl run."""
    if not Config.USE_SQLITE:
        return

    try:
        conn = await get_connection()
        await conn.execute(
            """
            UPDATE crawl_runs 
            SET end_time = CURRENT_TIMESTAMP, 
                status = 'completed',
                total_urls_visited = ?,
                total_application_pages = ?,
                total_actual_applications = ?
            WHERE run_id = ?
            """,
            (total_urls_visited, total_app_pages, total_actual_apps, run_id),
        )
        await conn.commit()
        logger.info(f"Recorded end of crawl run {run_id}")
    except Exception as e:
        logger.error(f"Failed to record crawl run end: {e}")
