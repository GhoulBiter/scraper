"""
Statistics tracking model for the crawler
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any
from datetime import datetime
import time

from config import Config
from models.application_page import ApplicationPage, ApplicationPageCollection


@dataclass
class CrawlStats:
    """Statistics for a crawl session."""

    # Timing stats
    start_time: float = field(default_factory=time.time)
    last_checkpoint_time: float = field(default_factory=time.time)

    # URL counters
    total_urls_visited: int = 0
    total_urls_queued: int = 0

    # Domain tracking
    domain_visit_counts: Dict[str, int] = field(default_factory=dict)
    admission_related_domains: Set[str] = field(default_factory=set)

    # Page tracking
    application_pages: ApplicationPageCollection = field(
        default_factory=ApplicationPageCollection
    )
    evaluated_pages: ApplicationPageCollection = field(
        default_factory=ApplicationPageCollection
    )

    def update_checkpoint(self) -> None:
        """Update the checkpoint time."""
        self.last_checkpoint_time = time.time()

    def elapsed_since_start(self) -> float:
        """Get elapsed time since start in seconds."""
        return time.time() - self.start_time

    def elapsed_since_checkpoint(self) -> float:
        """Get elapsed time since last checkpoint in seconds."""
        return time.time() - self.last_checkpoint_time

    def current_crawl_rate(self, urls_since_checkpoint: int) -> float:
        """Calculate the current crawl rate in URLs/second."""
        elapsed = self.elapsed_since_checkpoint()
        if elapsed <= 0:
            return 0
        return urls_since_checkpoint / elapsed

    def add_domain_visit(self, domain: str) -> None:
        """Increment the visit count for a domain."""
        if domain not in self.domain_visit_counts:
            self.domain_visit_counts[domain] = 0
        self.domain_visit_counts[domain] += 1

        # Check if we've reached the max URLs for a domain
        if self.domain_visit_counts[domain] >= Config.MAX_URLS_PER_DOMAIN:
            return False
        return True

    def add_admission_domain(self, domain: str) -> None:
        """Add an admission-related domain."""
        self.admission_related_domains.add(domain)

    def add_application_page(self, page_data: Dict[str, Any]) -> None:
        """Add a found application page."""
        page = ApplicationPage.from_dict(page_data)
        self.application_pages.add(page)

    def add_evaluated_page(self, page_data: Dict[str, Any]) -> None:
        """Add an evaluated application page."""
        page = ApplicationPage.from_dict(page_data)
        self.evaluated_pages.add(page)

    def get_top_domains(self, limit: int = 5) -> List[tuple]:
        """Get the top visited domains."""
        return sorted(
            self.domain_visit_counts.items(), key=lambda x: x[1], reverse=True
        )[:limit]

    def should_enforce_url_limit(self) -> bool:
        """Check if we should enforce the URL limit."""
        return self.total_urls_queued >= Config.MAX_TOTAL_URLS


@dataclass
class APIMetrics:
    """Tracking for API usage metrics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    pages_evaluated: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    model: Optional[str] = None
    university: Optional[str] = None

    def add_usage(
        self, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0
    ) -> None:
        """Add API usage for a request."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.pages_evaluated += 1

        # Get token rates from Config instead of hardcoding
        rate_per_1k_input = Config.PROMPT_TOKEN_COST
        rate_per_1k_completion = Config.COMPLETION_TOKEN_COST
        rate_per_1k_cached_input = Config.CACHED_TOKEN_COST

        request_cost = (
            (prompt_tokens / 1000) * rate_per_1k_input
            + (cached_tokens / 1000) * rate_per_1k_cached_input
            + (completion_tokens / 1000) * rate_per_1k_completion
        )

        self.estimated_cost_usd += request_cost

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "pages_evaluated": self.pages_evaluated,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "university": self.university,
        }
