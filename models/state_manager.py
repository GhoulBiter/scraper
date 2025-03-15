"""
State manager to handle shared crawler state with proper synchronization
"""

import asyncio
from typing import Dict, Set, List, Any
from loguru import logger


class CrawlerState:
    """Thread-safe state manager for the crawler."""

    def __init__(self):
        # URL tracking
        self.visited_urls = set()
        self.total_urls_visited = 0
        self.total_urls_queued = 0

        # Domain tracking
        self.domain_visit_counts = {}
        self.admission_related_domains = set()

        # Application pages
        self.found_applications = []
        self.evaluated_applications = []

        # Runtime control
        self.crawler_running = True

        # Locks for thread safety
        self.url_counter_lock = asyncio.Lock()
        self.visited_urls_lock = asyncio.Lock()
        self.domain_lock = asyncio.Lock()
        self.applications_lock = asyncio.Lock()
        self.admission_domains_lock = asyncio.Lock()
        self.crawler_status_lock = asyncio.Lock()

    # URL tracking methods
    async def add_visited_url(self, url: str) -> None:
        """Add a URL to the visited set with proper locking."""
        async with self.visited_urls_lock:
            self.visited_urls.add(url)

    async def is_url_visited(self, url: str) -> bool:
        """Check if a URL has been visited with proper locking."""
        async with self.visited_urls_lock:
            return url in self.visited_urls

    async def increment_visited_counter(self) -> int:
        """Increment the visited URLs counter with proper locking."""
        async with self.url_counter_lock:
            self.total_urls_visited += 1
            return self.total_urls_visited

    async def increment_queued_counter(self) -> int:
        """Increment the queued URLs counter with proper locking."""
        async with self.url_counter_lock:
            self.total_urls_queued += 1
            return self.total_urls_queued

    async def get_counters(self) -> Dict[str, int]:
        """Get the current counter values with proper locking."""
        async with self.url_counter_lock:
            return {
                "visited": self.total_urls_visited,
                "queued": self.total_urls_queued,
            }

    # Domain tracking methods
    async def increment_domain_count(self, domain: str) -> int:
        """Increment the count for a domain with proper locking."""
        async with self.domain_lock:
            if domain not in self.domain_visit_counts:
                self.domain_visit_counts[domain] = 0
            self.domain_visit_counts[domain] += 1
            return self.domain_visit_counts[domain]

    async def get_domain_counts(self) -> Dict[str, int]:
        """Get the current domain visit counts with proper locking."""
        async with self.domain_lock:
            return self.domain_visit_counts.copy()

    async def get_top_domains(self, limit: int = 5) -> List[tuple]:
        """Get the top visited domains with proper locking."""
        async with self.domain_lock:
            return sorted(
                self.domain_visit_counts.items(), key=lambda x: x[1], reverse=True
            )[:limit]

    # Application tracking methods
    async def add_application_page(self, page: Dict[str, Any]) -> None:
        """Add a found application page with proper locking."""
        async with self.applications_lock:
            self.found_applications.append(page)

    async def add_evaluated_page(self, page: Dict[str, Any]) -> None:
        """Add an evaluated application page with proper locking."""
        async with self.applications_lock:
            self.evaluated_applications.append(page)

    async def get_application_pages(self) -> List[Dict[str, Any]]:
        """Get the current application pages with proper locking."""
        async with self.applications_lock:
            return self.found_applications.copy()

    async def get_evaluated_pages(self) -> List[Dict[str, Any]]:
        """Get the evaluated application pages with proper locking."""
        async with self.applications_lock:
            return self.evaluated_applications.copy()

    # Admission domains tracking
    async def add_admission_domain(self, domain: str) -> None:
        """Add an admission-related domain with proper locking."""
        async with self.admission_domains_lock:
            self.admission_related_domains.add(domain)

    async def get_admission_domains(self) -> Set[str]:
        """Get the current admission domains with proper locking."""
        async with self.admission_domains_lock:
            return self.admission_related_domains.copy()

    # Crawler control methods
    async def stop_crawler(self) -> None:
        """Signal the crawler to stop with proper locking."""
        async with self.crawler_status_lock:
            self.crawler_running = False
            logger.info("Crawler stop requested")

    async def is_crawler_running(self) -> bool:
        """Check if the crawler is running with proper locking."""
        async with self.crawler_status_lock:
            return self.crawler_running

    # URL limit checking
    async def should_enforce_url_limit(self, limit: int) -> bool:
        """Check if we should enforce the URL limit with proper locking."""
        async with self.url_counter_lock:
            return self.total_urls_queued >= limit


# Create a global state manager instance
state_manager = CrawlerState()
