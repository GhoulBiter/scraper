"""
Priority queue implementation for the crawler
"""

import asyncio
from loguru import logger

from models.state_manager import state_manager
from config import Config


class UniqueURLQueue:
    """A queue that ensures each URL is processed only once with priority support."""

    def __init__(self, maxsize=0):
        self.queue = asyncio.PriorityQueue(maxsize)
        self.url_set = set()
        self.lock = asyncio.Lock()
        self.current_size = 0
        self.max_memory_size = 10000  # Maximum number of items in queue

    async def put(self, item):
        """Put an item in the queue if it's not already there and under the limit."""
        priority, url, depth, university = item

        # First check URL limit before anything else
        if await state_manager.should_enforce_url_limit(Config.MAX_TOTAL_URLS):
            # Don't log every time - this was causing log bloat
            return False

        async with self.lock:
            if url not in self.url_set:
                self.url_set.add(url)

                # Check if queue is getting too large
                if self.current_size >= self.max_memory_size:
                    # Discard the lowest priority (highest number) items
                    logger.warning(
                        f"Queue size limit reached ({self.max_memory_size}), prioritizing high-value URLs"
                    )
                    return False

                # Register URL as visited immediately to prevent duplicates
                await state_manager.add_visited_url(url)

                # Increment queued counter
                await state_manager.increment_queued_counter()

                # Add to queue
                await self.queue.put(item)
                self.current_size += 1
                return True

        return False

    async def get(self):
        """Get an item from the queue."""
        item = await self.queue.get()
        self.current_size -= 1
        return item

    def task_done(self):
        """Mark a task as done."""
        self.queue.task_done()

    async def join(self):
        """Wait for all items to be processed."""
        await self.queue.join()

    def empty(self):
        """Check if the queue is empty."""
        return self.queue.empty()

    def qsize(self):
        """Get the queue size."""
        return self.current_size
