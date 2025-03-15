"""
Link extraction and processing utilities
"""

import re
from urllib.parse import urljoin

from loguru import logger

from utils.url_utils import is_valid_url, normalize_url


def extract_links(url, html):
    """Extract links from HTML content."""
    if not html:
        return []

    base_url = url
    links = []

    # Extract all links
    href_matches = re.findall(r'<a[^>]*href=["\'](.*?)["\']', html, re.IGNORECASE)

    for href in href_matches:
        # Skip empty links, javascript, mailto, tel links
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Normalize URL
        normalized = normalize_url(full_url)

        # Check if valid (this will be imported from url_utils)
        if is_valid_url(normalized):
            links.append(normalized)

    return links
