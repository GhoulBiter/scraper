"""
Data model for application pages
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
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
        )


class ApplicationPageCollection:
    """Collection of application pages with filtering and grouping capabilities."""

    def __init__(self, pages: List[ApplicationPage] = None):
        self.pages = pages or []

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

    @classmethod
    def from_dict_list(cls, data: List[Dict[str, Any]]) -> "ApplicationPageCollection":
        """Create a collection from a list of dictionaries."""
        pages = [ApplicationPage.from_dict(item) for item in data]
        return cls(pages=pages)
