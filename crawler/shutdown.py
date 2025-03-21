"""
Graceful shutdown implementation
"""

import asyncio
import signal
import time
from loguru import logger

# Flag to track shutdown requests
_shutdown_requested = False


class GracefulShutdown:
    """Manages graceful shutdown of worker tasks."""

    def __init__(self):
        self.shutdown_requested = False
        self.shutdown_lock = asyncio.Lock()
        self.active_tasks = set()
        self.task_lock = asyncio.Lock()

    async def request_shutdown(self):
        """Request shutdown of all workers."""
        async with self.shutdown_lock:
            self.shutdown_requested = True
            logger.info("Shutdown requested, waiting for active tasks to complete...")

    async def is_shutdown_requested(self):
        """Check if shutdown has been requested."""
        async with self.shutdown_lock:
            return self.shutdown_requested

    async def register_task(self, task_id, url):
        """Register an active task."""
        async with self.task_lock:
            self.active_tasks.add((task_id, url))

    async def unregister_task(self, task_id, url):
        """Unregister a completed task."""
        async with self.task_lock:
            self.active_tasks.discard((task_id, url))

    async def get_active_tasks(self):
        """Get list of currently active tasks."""
        async with self.task_lock:
            return list(self.active_tasks)

    async def wait_for_completion(self, timeout=30):
        """Wait for all active tasks to complete with timeout."""
        start_time = time.time()
        while True:
            active = await self.get_active_tasks()
            if not active:
                return True

            if time.time() - start_time > timeout:
                logger.warning(
                    f"Shutdown timeout exceeded with {len(active)} tasks still active"
                )
                return False

            logger.info(f"Waiting for {len(active)} active tasks to complete...")
            await asyncio.sleep(1)


# Initialize the global shutdown controller
shutdown_controller = GracefulShutdown()


# Global flag for signal handlers (which are synchronous)
def signal_handler(signum, frame):
    """Synchronous signal handler that sets a global flag."""
    global _shutdown_requested
    logger.info("\nReceived exit signal. Shutting down gracefully...")
    _shutdown_requested = True


async def check_for_shutdown():
    """Async function to check if a shutdown was requested by signal handler."""
    global _shutdown_requested
    if _shutdown_requested:
        _shutdown_requested = False  # Reset flag
        await shutdown_controller.request_shutdown()
        return True
    return False


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
