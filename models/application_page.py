"""
Data model for application pages
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Iterator
from datetime import datetime


@dataclass
class ApplicationPage:
    """Represents a university application page."""

    url: str
    title: str
    university: str
    reasons: List[str] = field(default_factory=list)
    depth: int = 0
    is_actual_application: bool = False
    ai_evaluation: Optional[str] = None
    html_snippet: Optional[str] = None
    found_timestamp: datetime = field(default_factory=datetime.now)
    application_type: str = "information_only"
    category: int = 4  # Default is information_only (category 4)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "url": self.url,
            "title": self.title,
            "university": self.university,
            "reasons": self.reasons,
            "depth": self.depth,
            "is_actual_application": self.is_actual_application,
            "ai_evaluation": self.ai_evaluation,
            "application_type": self.application_type,
            "category": self.category,
            "found_timestamp": self.found_timestamp.isoformat(),
        }

        # Only include html_snippet if it exists
        if self.html_snippet:
            result["html_snippet"] = self.html_snippet

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationPage":
        """Create an ApplicationPage from a dictionary."""
        # Handle timestamp conversion
        found_timestamp = data.get("found_timestamp")
        if isinstance(found_timestamp, str):
            try:
                found_timestamp = datetime.fromisoformat(found_timestamp)
            except ValueError:
                found_timestamp = datetime.now()

        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            university=data.get("university", ""),
            reasons=data.get("reasons", []),
            depth=data.get("depth", 0),
            is_actual_application=data.get("is_actual_application", False),
            ai_evaluation=data.get("ai_evaluation"),
            html_snippet=data.get("html_snippet"),
            found_timestamp=found_timestamp or datetime.now(),
            application_type=data.get("application_type", "information_only"),
            category=data.get("category", 4),
        )


class ApplicationPageCollection:
    """Collection of application pages with filtering and grouping capabilities."""

    def __init__(self, pages: List[ApplicationPage] = None):
        self.pages = pages or []

    def __iter__(self) -> Iterator[ApplicationPage]:
        """Make the collection iterable, returning an iterator of pages."""
        return iter(self.pages)

    def __len__(self) -> int:
        """Return the number of pages in the collection."""
        return len(self.pages)

    def add(self, page: ApplicationPage) -> None:
        """Add a page to the collection."""
        self.pages.append(page)

    def filter_actual_applications(self) -> List[ApplicationPage]:
        """Get only the confirmed application pages."""
        return [p for p in self.pages if p.is_actual_application]

    def group_by_university(self) -> Dict[str, List[ApplicationPage]]:
        """Group pages by university."""
        result = {}
        for page in self.pages:
            if page.university not in result:
                result[page.university] = []
            result[page.university].append(page)
        return result

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert to a list of dictionaries for serialization."""
        return [page.to_dict() for page in self.pages]

    def filter_by_category(self, category: int) -> List[ApplicationPage]:
        """Get pages of a specific category."""
        return [p for p in self.pages if p.category == category]

    def filter_by_type(self, app_type: str) -> List[ApplicationPage]:
        """Get pages of a specific application type."""
        return [p for p in self.pages if p.application_type == app_type]

    def get_category_counts(self) -> Dict[int, int]:
        """Count pages by category."""
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for page in self.pages:
            if page.category in counts:
                counts[page.category] += 1
        return counts

    @classmethod
    def from_dict_list(cls, data: List[Dict[str, Any]]) -> "ApplicationPageCollection":
        """Create a collection from a list of dictionaries."""
        pages = [ApplicationPage.from_dict(item) for item in data]
        return cls(pages=pages)
