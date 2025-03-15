"""
Worker implementation for processing URLs from the queue
"""

import asyncio
import time
from loguru import logger

from crawler.shutdown import shutdown_controller
from crawler.fetcher import fetch_url
from models.state_manager import state_manager

from config import Config


async def worker(session, worker_id, url_queue):
    """Worker to process URLs from the queue."""
    logger.info(f"Worker {worker_id} started")

    while await state_manager.is_crawler_running():
        try:
            # Check if shutdown requested
            if await shutdown_controller.is_shutdown_requested():
                logger.info(f"Worker {worker_id} shutting down due to shutdown request")
                break

            # Get URL with timeout to allow for shutdown checks
            try:
                priority, url, depth, university = await asyncio.wait_for(
                    url_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Register this task
            task_id = f"worker-{worker_id}-{time.time()}"
            await shutdown_controller.register_task(task_id, url)

            try:
                # Check URL limit before processing
                counters = await state_manager.get_counters()
                if counters["queued"] >= Config.MAX_TOTAL_URLS:
                    logger.debug(f"Skipping {url} due to URL limit")
                    continue

                # Process URL
                await fetch_url(session, url, depth, university, url_queue)
            finally:
                # Always unregister task when done or on exception
                await shutdown_controller.unregister_task(task_id, url)
                # Mark task as done
                url_queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} cancelled")
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")

    logger.info(f"Worker {worker_id} shutting down")


async def start_workers(session, url_queue, num_workers=None):
    """Start a pool of worker tasks."""

    if num_workers is None:
        num_workers = Config.NUM_WORKERS

    workers = []
    for i in range(num_workers):
        worker_task = asyncio.create_task(worker(session, i, url_queue))
        workers.append(worker_task)

    return workers
