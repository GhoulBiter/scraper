"""
Priority queue implementation for the crawler with domain-based prioritization and queue size management
"""

import asyncio
import time
import heapq
from collections import defaultdict
from loguru import logger

from models.state_manager import state_manager
from config import Config


class UniqueURLQueue:
    """A queue that ensures each URL is processed only once with prioritization by domain and depth."""

    def __init__(self, maxsize=0):
        self.queue = asyncio.PriorityQueue(maxsize)
        self.url_set = set()
        self.lock = asyncio.Lock()
        self.domain_locks = defaultdict(
            asyncio.Lock
        )  # Per-domain locks for rate limiting
        self.domain_counts = defaultdict(int)  # Track URL counts per domain
        self.domain_last_access = defaultdict(
            float
        )  # Track last access time per domain
        self.current_size = 0
        self.max_memory_size = 10000  # Maximum number of items in queue
        self.max_per_domain = 500  # Maximum URLs queued per domain
        self.domain_rate_limit = 1.0  # Minimum seconds between requests to same domain

    async def put(self, item):
        """Put an item in the queue if it's not already there and under the limit."""
        priority, url, depth, university = item

        # First check URL limit before anything else
        if await state_manager.should_enforce_url_limit(Config.MAX_TOTAL_URLS):
            return False

        # Extract domain for domain-specific limits
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()

        async with self.lock:
            # Check if URL is already in the queue
            if url in self.url_set:
                return False

            # Add to URL set for duplicate checking
            self.url_set.add(url)

            # Check domain-specific limits
            if self.domain_counts[domain] >= self.max_per_domain:
                # Only log if it's a potentially important URL based on low priority value
                if priority < 5:
                    logger.debug(f"Domain limit reached for {domain}, skipping {url}")
                return False

            # Check if queue is getting too large - prioritize if needed
            if self.current_size >= self.max_memory_size:
                # Only allow high priority items when queue is full (lower number = higher priority)
                if priority > 3:
                    # Skip low-priority URLs when queue is full
                    return False
                else:
                    logger.info(f"Queue full but accepting high-priority URL: {url}")

            # Register URL as visited immediately to prevent duplicates
            await state_manager.add_visited_url(url)

            # Increment counters
            await state_manager.increment_queued_counter()
            self.domain_counts[domain] += 1

            # If depth is below threshold, adjust priority to explore less
            if depth < 0 or depth >= Config.MAX_DEPTH - 3:
                # De-prioritize very deep URLs
                priority += 5

            # Add to queue
            await self.queue.put(item)
            self.current_size += 1
            return True

    async def get(self):
        """Get an item from the queue with domain-based rate limiting."""
        while True:
            item = await self.queue.get()
            priority, url, depth, university = item

            # Extract domain for rate limiting
            from urllib.parse import urlparse

            domain = urlparse(url).netloc.lower()

            # Check domain rate limiting
            current_time = time.time()
            async with self.domain_locks[domain]:
                time_since_last = current_time - self.domain_last_access[domain]

                if time_since_last < self.domain_rate_limit:
                    # If too soon, put back in queue with reduced priority and wait
                    await self.queue.put((priority + 1, url, depth, university))
                    await asyncio.sleep(0.1)  # Small delay to avoid CPU spinning
                    continue

                # Update last access time for this domain
                self.domain_last_access[domain] = current_time

                # Decrement domain counter
                self.domain_counts[domain] = max(0, self.domain_counts[domain] - 1)
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

    async def get_domain_stats(self):
        """Get statistics about domains in the queue."""
        async with self.lock:
            total_domains = len(self.domain_counts)
            top_domains = sorted(
                self.domain_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
            return {"total_domains": total_domains, "top_domains": top_domains}
