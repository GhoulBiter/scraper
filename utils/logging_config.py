"""
Logging configuration using Loguru
"""

import sys
from loguru import logger


def configure_logging(log_file="crawler.log", log_level="INFO"):
    """Configure Loguru logger with appropriate formats and outputs."""
    # Remove default handler
    logger.remove()

    # Add stderr handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # Add file handler with rotation
    logger.add(
        log_file,
        rotation="10 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=log_level,
    )

    # Add special file handler for errors only
    logger.add(
        "errors.log",
        rotation="5 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}\n{exception}",
        level="ERROR",
        backtrace=True,
        diagnose=True,
    )

    logger.info("Logging configured successfully")


def get_custom_logger(name):
    """Get a logger with context information."""
    return logger.bind(name=name)


# Define custom log levels
def add_custom_levels():
    """Add custom log levels for the crawler."""
    # Success level for found application pages
    logger.level("SUCCESS", no=25, color="<green>")

    # Special level for crawler insights
    logger.level("INSIGHT", no=15, color="<cyan>")


# Define custom log formats for specific contexts
def add_log_context(crawler_name, run_id):
    """Add custom context to log messages."""
    logger.configure(extra={"crawler": crawler_name, "run_id": run_id})

    # Now you can access these in format strings like:
    # format="{extra[crawler]} | {extra[run_id]} | {message}"
