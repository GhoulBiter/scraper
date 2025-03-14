# database.py
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from loguru import logger

# Thread pool for database operations
db_executor = ThreadPoolExecutor(max_workers=4)  # Limit concurrent DB operations


async def init_database():
    """Initialize SQLite database asynchronously."""

    def _init_db():
        try:
            with sqlite3.connect("crawler_metrics.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    university TEXT,
                    model TEXT,
                    pages_evaluated INTEGER,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    estimated_cost_usd REAL,
                    run_id TEXT
                )
                """
                )
                conn.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    # Run in thread pool to avoid blocking
    await asyncio.get_event_loop().run_in_executor(db_executor, _init_db)


async def save_metrics_to_db(metrics, run_id):
    """Save metrics to database asynchronously."""

    def _save_metrics(metrics_data, run_id):
        try:
            with sqlite3.connect("crawler_metrics.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                INSERT INTO api_usage 
                (timestamp, university, model, pages_evaluated, prompt_tokens, 
                 completion_tokens, total_tokens, estimated_cost_usd, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metrics_data["timestamp"],
                        metrics_data["university"],
                        metrics_data["model"],
                        metrics_data["pages_evaluated"],
                        metrics_data["prompt_tokens"],
                        metrics_data["completion_tokens"],
                        metrics_data["total_tokens"],
                        metrics_data["estimated_cost_usd"],
                        run_id,
                    ),
                )
                conn.commit()
                logger.info(f"Saved API metrics to database for run {run_id}")
        except Exception as e:
            logger.error(f"Error saving metrics to database: {e}")

    # Run in thread pool to avoid blocking
    await asyncio.get_event_loop().run_in_executor(
        db_executor, lambda: _save_metrics(metrics, run_id)
    )


async def get_aggregated_metrics(period="all"):
    """Get aggregated API usage metrics for reporting."""

    def _get_metrics(period):
        try:
            with sqlite3.connect("crawler_metrics.db") as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Define time period filter
                time_filter = ""
                if period == "day":
                    time_filter = "WHERE timestamp >= datetime('now', '-1 day')"
                elif period == "week":
                    time_filter = "WHERE timestamp >= datetime('now', '-7 day')"
                elif period == "month":
                    time_filter = "WHERE timestamp >= datetime('now', '-30 day')"

                query = f"""
                SELECT 
                    COUNT(*) as total_runs,
                    SUM(pages_evaluated) as total_pages,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(estimated_cost_usd) as total_cost
                FROM api_usage
                {time_filter}
                """
                cursor.execute(query)
                result = dict(cursor.fetchone())
                return result
        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {e}")
            return {
                "total_runs": 0,
                "total_pages": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0,
            }

    # Run in thread pool to avoid blocking
    return await asyncio.get_event_loop().run_in_executor(
        db_executor, lambda: _get_metrics(period)
    )
