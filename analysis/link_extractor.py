"""
Improved link extraction with proper HTML parsing
Replaces regex-based extraction with HTML parser
"""

import asyncio
from urllib.parse import urljoin, urlparse, unquote
from html.parser import HTMLParser
from loguru import logger

from utils.url_utils import is_valid_url, normalize_url


class LinkExtractorParser(HTMLParser):
    """HTML Parser specifically for extracting links."""

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            # Extract href attribute
            for attr, value in attrs:
                if attr == "href" and value:
                    # Skip empty links, javascript, mailto, tel links, and fragments
                    if not value or value.startswith(
                        ("javascript:", "mailto:", "tel:", "#")
                    ):
                        continue

                    # Clean the URL - handle URL encoding issues
                    try:
                        # Decode any URL encoded characters
                        value = unquote(value)

                        # Remove any HTML that might be part of the URL
                        if "<" in value or ">" in value:
                            value = value.split("<")[0].split(">")[0]

                        # Resolve relative URLs
                        full_url = urljoin(self.base_url, value)

                        # Normalize URL
                        normalized = normalize_url(full_url)

                        # Validate URL and add to list
                        if normalized and is_valid_url(normalized):
                            # Check for suspicious URL patterns
                            if self._is_suspicious_url(normalized):
                                logger.warning(f"Skipping suspicious URL: {normalized}")
                                continue

                            self.links.append(normalized)
                    except Exception as e:
                        logger.debug(f"Error processing URL {value}: {e}")

    def _is_suspicious_url(self, url):
        """Check for suspicious URL patterns that might indicate a loop."""
        try:
            parsed = urlparse(url)
            path = parsed.path

            # Check for repeating patterns in the path
            path_parts = [p for p in path.split("/") if p]

            # Look for the same path component repeated multiple times in sequence
            for i in range(len(path_parts) - 1):
                if path_parts[i] == path_parts[i + 1]:
                    return True

            # Check for unusually long paths (may indicate a loop)
            if len(path_parts) > 15:  # Arbitrary threshold for demonstration
                return True

            # Check for malformed URLs containing HTML tags or unusual characters
            suspicious_chars = ["<", ">", '"', "'", "%22", "%3C", "%3E"]
            if any(char in url for char in suspicious_chars):
                return True

            return False
        except Exception:
            # If we can't parse it, consider it suspicious
            return True


def extract_links(url, html):
    """Extract links from HTML content using proper HTML parsing."""
    if not html:
        return []

    # Initialize parser
    parser = LinkExtractorParser(url)

    try:
        # Feed HTML to parser
        parser.feed(html)
        return parser.links
    except Exception as e:
        logger.error(f"Error extracting links from {url}: {e}")
        return []
