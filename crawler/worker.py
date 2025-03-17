"""
Worker implementation for processing URLs from the queue with improved handling
"""

import asyncio
import time
from datetime import datetime
from loguru import logger

from crawler.shutdown import shutdown_controller
from crawler.fetcher import fetch_url
from models.state_manager import state_manager

from config import Config


async def worker(session, worker_id, url_queue):
    """Worker to process URLs from the queue with adaptive behavior."""
    logger.info(f"Worker {worker_id} started")
    urls_processed = 0
    start_time = time.time()
    errors = 0
    consecutive_timeouts = 0

    while await state_manager.is_crawler_running():
        try:
            # Check if shutdown requested
            if await shutdown_controller.is_shutdown_requested():
                logger.info(f"Worker {worker_id} shutting down due to shutdown request")
                break

            # Get URL with timeout to allow for shutdown checks
            try:
                item = await asyncio.wait_for(url_queue.get(), timeout=1.0)
                priority, url, depth, university = item
            except asyncio.TimeoutError:
                # If queue is empty for a while, log occasional updates
                if urls_processed > 0 and (time.time() - start_time) > 60:
                    rate = urls_processed / (time.time() - start_time)
                    logger.debug(
                        f"Worker {worker_id}: {urls_processed} URLs processed ({rate:.2f}/sec)"
                    )
                continue
            except asyncio.CancelledError:
                break

            # Register this task
            task_id = f"worker-{worker_id}-{time.time()}"
            await shutdown_controller.register_task(task_id, url)

            try:
                # Log current task with depth and priority
                logger.debug(
                    f"Worker {worker_id} processing: {url} (depth={depth}, priority={priority})"
                )

                # Check URL limit before processing
                counters = await state_manager.get_counters()
                if counters["queued"] >= Config.MAX_TOTAL_URLS:
                    logger.debug(f"Skipping {url} due to URL limit")
                    continue

                # Process URL with timeout
                try:
                    # Use the correct timeout from Config
                    timeout_value = 20  # Default timeout if not in Config
                    if hasattr(Config, "REQUEST_TIMEOUT"):
                        timeout_value = Config.REQUEST_TIMEOUT + 5

                    # Make sure to await the coroutine
                    await asyncio.wait_for(
                        fetch_url(session, url, depth, university, url_queue),
                        timeout=timeout_value,  # Add buffer time to the request timeout
                    )
                    urls_processed += 1
                    consecutive_timeouts = 0  # Reset timeout counter on success
                except asyncio.TimeoutError:
                    logger.warning(f"Worker {worker_id} timeout processing {url}")
                    consecutive_timeouts += 1

                    # If we're having many timeouts, slow down this worker
                    if consecutive_timeouts >= 3:
                        logger.warning(
                            f"Worker {worker_id} experiencing consecutive timeouts, backing off"
                        )
                        await asyncio.sleep(
                            consecutive_timeouts * 2
                        )  # Exponential backoff

                # Log processing rate periodically
                if urls_processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = urls_processed / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Worker {worker_id} has processed {urls_processed} URLs ({rate:.2f}/sec)"
                    )

            except Exception as e:
                logger.error(f"Worker {worker_id} error processing {url}: {e}")
                errors += 1

                # If we're having too many errors, slow down
                if errors > 10:
                    logger.warning(
                        f"Worker {worker_id} experiencing many errors, slowing down"
                    )
                    await asyncio.sleep(
                        min(2.0, errors * 0.1)
                    )  # Gradually increase delay

                    # Reset error counter periodically
                    if time.time() - start_time > 600:  # Every 10 minutes
                        errors = 0
                        start_time = time.time()

            finally:
                # Always unregister task when done or on exception
                await shutdown_controller.unregister_task(task_id, url)
                # Mark task as done
                url_queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} cancelled")
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} unexpected error: {e}")
            await asyncio.sleep(1)  # Avoid tight loop on persistent errors

    logger.info(f"Worker {worker_id} shutting down. Processed {urls_processed} URLs")


async def start_workers(session, url_queue, num_workers=None):
    """Start a pool of worker tasks with adaptive sizing."""

    if num_workers is None:
        num_workers = Config.NUM_WORKERS

    # Log worker pool setup
    logger.info(f"Starting {num_workers} workers for URL processing")

    workers = []
    for i in range(num_workers):
        worker_task = asyncio.create_task(worker(session, i, url_queue))
        workers.append(worker_task)

        # Stagger worker startup slightly to avoid all workers hitting the same domain at once
        await asyncio.sleep(0.05)

    # Add monitoring task for worker health
    monitor_task = asyncio.create_task(monitor_workers(workers, url_queue))
    workers.append(monitor_task)

    return workers


async def monitor_workers(workers, url_queue):
    """Monitor worker health and queue size, adjusting behavior as needed."""
    while True:
        try:
            # Check if crawler is still running
            if not await state_manager.is_crawler_running():
                break

            # Get queue size
            queue_size = url_queue.qsize()
            domain_stats = await url_queue.get_domain_stats()

            # Log queue status every 30 seconds
            logger.info(
                f"Queue status: {queue_size} URLs queued across {domain_stats['total_domains']} domains"
            )

            if domain_stats["top_domains"]:
                top_domains_str = ", ".join(
                    f"{domain}:{count}"
                    for domain, count in domain_stats["top_domains"][:5]
                )
                logger.info(f"Top domains in queue: {top_domains_str}")

            # Check if the queue is growing too large
            if queue_size > Config.MAX_QUEUE_SIZE * 0.9:
                logger.warning(
                    f"Queue size ({queue_size}) approaching limit, consider more aggressive filtering"
                )

            # Wait before next check
            await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Worker monitor cancelled")
            break
        except Exception as e:
            logger.error(f"Error in worker monitor: {e}")
            await asyncio.sleep(5)
