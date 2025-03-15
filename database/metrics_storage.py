"""
Metrics storage and retrieval functionality
"""

import datetime
from loguru import logger

from database.db_operations import get_connection
from config import Config


async def save_metrics_to_db(metrics, run_id):
    """Save API metrics to the database."""
    if not Config.USE_SQLITE:
        return

    try:
        conn = await get_connection()
        await conn.execute(
            """
            INSERT INTO api_metrics
            (run_id, timestamp, model, prompt_tokens, completion_tokens, 
             total_tokens, pages_evaluated, estimated_cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                metrics.get(
                    "timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ),
                metrics.get("model", Config.MODEL_NAME),
                metrics.get("prompt_tokens", 0),
                metrics.get("completion_tokens", 0),
                metrics.get("total_tokens", 0),
                metrics.get("pages_evaluated", 0),
                metrics.get("estimated_cost_usd", 0.0),
            ),
        )
        await conn.commit()
        logger.info(f"Saved API metrics to database for run {run_id}")
    except Exception as e:
        logger.error(f"Failed to save API metrics: {e}")
        raise


async def save_application_page(page, run_id):
    """Save an application page to the database."""
    if not Config.USE_SQLITE:
        return

    try:
        conn = await get_connection()
        await conn.execute(
            """
            INSERT INTO application_pages
            (run_id, url, title, university, depth, is_actual_application, ai_evaluation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                page.get("url", ""),
                page.get("title", ""),
                page.get("university", ""),
                page.get("depth", 0),
                1 if page.get("is_actual_application", False) else 0,
                page.get("ai_evaluation", ""),
            ),
        )
        await conn.commit()
    except Exception as e:
        logger.error(f"Failed to save application page: {e}")


async def save_application_pages(pages, run_id):
    """Save multiple application pages to the database."""
    if not Config.USE_SQLITE or not pages:
        return

    try:
        conn = await get_connection()
        async with conn.cursor() as cursor:
            for page in pages:
                await cursor.execute(
                    """
                    INSERT INTO application_pages
                    (run_id, url, title, university, depth, is_actual_application, ai_evaluation)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        page.get("url", ""),
                        page.get("title", ""),
                        page.get("university", ""),
                        page.get("depth", 0),
                        1 if page.get("is_actual_application", False) else 0,
                        page.get("ai_evaluation", ""),
                    ),
                )
            await conn.commit()
        logger.info(f"Saved {len(pages)} application pages to database")
    except Exception as e:
        logger.error(f"Failed to save application pages: {e}")


async def get_aggregated_metrics(period="month"):
    """Get aggregated API metrics for a specific time period."""
    if not Config.USE_SQLITE:
        return {
            "total_runs": 0,
            "total_pages": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    try:
        conn = await get_connection()

        # Define date filter based on period
        date_filter = ""
        if period == "day":
            date_filter = "AND timestamp >= datetime('now', '-1 day')"
        elif period == "week":
            date_filter = "AND timestamp >= datetime('now', '-7 days')"
        elif period == "month":
            date_filter = "AND timestamp >= datetime('now', '-30 days')"

        # Query for metrics
        query = f"""
        SELECT 
            COUNT(DISTINCT run_id) as total_runs,
            SUM(pages_evaluated) as total_pages,
            SUM(total_tokens) as total_tokens,
            SUM(estimated_cost_usd) as total_cost
        FROM api_metrics
        WHERE 1=1 {date_filter}
        """

        async with conn.execute(query) as cursor:
            row = await cursor.fetchone()

            if row:
                return {
                    "total_runs": row[0] or 0,
                    "total_pages": row[1] or 0,
                    "total_tokens": row[2] or 0,
                    "total_cost": row[3] or 0.0,
                }
            else:
                return {
                    "total_runs": 0,
                    "total_pages": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
    except Exception as e:
        logger.error(f"Failed to get aggregated metrics: {e}")
        # Return empty metrics on error
        return {
            "total_runs": 0,
            "total_pages": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }


async def get_recent_application_pages(university=None, limit=10):
    """Get recently found application pages."""
    if not Config.USE_SQLITE:
        return []

    try:
        conn = await get_connection()

        query = """
        SELECT url, title, university, is_actual_application, ai_evaluation, found_timestamp
        FROM application_pages
        """

        params = []
        if university:
            query += " WHERE university = ?"
            params.append(university)

        query += " ORDER BY found_timestamp DESC LIMIT ?"
        params.append(limit)

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            result = []
            for row in rows:
                result.append(
                    {
                        "url": row[0],
                        "title": row[1],
                        "university": row[2],
                        "is_actual_application": bool(row[3]),
                        "ai_evaluation": row[4],
                        "found_timestamp": row[5],
                    }
                )

            return result
    except Exception as e:
        logger.error(f"Failed to get recent application pages: {e}")
        return []
