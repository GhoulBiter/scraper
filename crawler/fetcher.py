"""
URL fetching implementation
"""

import asyncio
import random
import re
from urllib.parse import urljoin, urlparse

import aiohttp
from loguru import logger

from config import Config
from utils.encoding import EncodingHandler
from analysis.page_analyzer import is_application_page, extract_title
from analysis.link_extractor import (
    extract_links,
    is_valid_url,
    normalize_url,
)
from models.state_manager import state_manager
from utils.url_utils import get_url_priority, is_related_domain


async def fetch_url(session, url, depth, university, url_queue):
    """Fetch a URL and process its content."""
    # First check if the crawler is still running
    if not await state_manager.is_crawler_running():
        return

    # Normalize URL to handle Unicode
    normalized_url = EncodingHandler.normalize_url(url)
    if normalized_url != url:
        logger.info(f"Normalized URL: {url} -> {normalized_url}")
        url = normalized_url

    try:
        # Apply politeness delay
        await asyncio.sleep(Config.REQUEST_DELAY)

        # Log when fetching admission-related domains for debugging
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        if (
            "admission" in domain
            or "apply" in domain
            or "undergrad" in domain
            or any(p in path for p in ["/apply", "/admission", "/admissions"])
        ):
            logger.info(f"Fetching admission-related URL: {url} (depth {depth})")

        # Set up headers
        headers = {
            "User-Agent": Config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "DNT": "1",
        }

        # Use rotating user agents if configured
        if Config.USER_AGENT_ROTATION and Config.USER_AGENTS:
            headers["User-Agent"] = random.choice(Config.USER_AGENTS)

        # Fetch URL with headers
        async with session.get(
            url, timeout=Config.REQUEST_TIMEOUT, allow_redirects=True, headers=headers
        ) as response:
            if response.status != 200:
                logger.warning(f"Got status {response.status} for {url}")
                return

            # Increment visited counter and track domain
            await state_manager.increment_visited_counter()
            await state_manager.increment_domain_count(domain)

            # Log the final URL after any redirects
            if str(response.url) != url:
                logger.info(f"Redirected: {url} -> {response.url}")

            # Use encoding handler to properly decode HTML
            try:
                html = await EncodingHandler.decode_html(response)
            except Exception as e:
                logger.error(f"Error decoding HTML for {url}: {e}")
                return

            # Extract title with encoding awareness
            title = extract_title(html)

            # Check if this is an application page
            is_app_page, reasons = is_application_page(url, html, title)

            if is_app_page:
                logger.success(f"Found application page: {url} - {title}")
                logger.info(f"Reasons: {', '.join(reasons)}")

                await state_manager.add_application_page(
                    {
                        "url": url,
                        "title": title,
                        "university": university["name"],
                        "reasons": reasons,
                        "depth": depth,
                        "html_snippet": html[:5000],  # Save a snippet for evaluation
                    }
                )

            # Check if we're on an admission-related domain to increase depth
            if "admission" in domain or "apply" in domain or "undergrad" in domain:
                # Add to our set of admission domains
                await state_manager.add_admission_domain(domain)

                # Look for specific application links if we're in an admission domain
                apply_links = await find_critical_application_links(url, html)

                # Process these critical links with highest priority (depth doesn't matter)
                for link in apply_links:
                    # Use a high priority value (0) for critical application links
                    await url_queue.put(
                        (0, link, Config.MAX_DEPTH, university)
                    )  # Reset depth to ensure crawling

                # Don't extract more links if we've reached the max admission depth
                if depth <= 0 and depth > -Config.MAX_ADMISSION_DEPTH:
                    logger.info(f"Allowing extended depth for admission URL: {url}")
                    # Continue with negative depth to track extended crawling
                    depth = -1  # Start extended depth crawling
                elif depth < 0 and depth <= -Config.MAX_ADMISSION_DEPTH:
                    return
            # For normal domains, respect the regular depth
            elif depth <= 0:
                return

            # Check URL limit again before extracting links
            if await state_manager.should_enforce_url_limit(Config.MAX_TOTAL_URLS):
                return

            # Extract and queue links
            links = extract_links(url, html)
            await queue_links(links, depth - 1, university, url_queue)

    except aiohttp.ClientError as e:
        logger.error(f"Error fetching {url}: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
    except Exception as e:
        logger.error(f"Unexpected error processing {url}: {e}")


async def find_critical_application_links(url, html):
    """Find critical application links in admission-related pages."""
    apply_links = []
    apply_patterns = [
        r'<a[^>]*href=["\'](.*?apply.*?first-year.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?freshman.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?undergraduate.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?transfer.*?)["\']',
        r'<a[^>]*href=["\'](.*?admission.*?apply.*?)["\']',
    ]

    for pattern in apply_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for href in matches:
            full_url = urljoin(url, href)
            normalized = normalize_url(full_url)

            # Check if this URL has already been visited
            if not await state_manager.is_url_visited(normalized) and is_valid_url(
                normalized
            ):
                logger.info(f"Found critical application link: {normalized}")
                apply_links.append(normalized)

    return apply_links


async def queue_links(links, depth, university, url_queue):
    """Queue links for crawling with domain-specific rate limiting."""
    # Check URL limit before processing
    if await state_manager.should_enforce_url_limit(Config.MAX_TOTAL_URLS):
        return

    university_domain = university["domain"]
    domain_queue = []

    for link in links:
        # Check if crawler is still running
        if not await state_manager.is_crawler_running():
            return

        parsed = urlparse(link)
        domain = parsed.netloc

        # Skip if we've reached the max URLs for a domain
        domain_counts = await state_manager.get_domain_counts()
        if (
            domain in domain_counts
            and domain_counts[domain] >= Config.MAX_URLS_PER_DOMAIN
        ):
            continue

        # Skip if we've reached the max total URLs
        counters = await state_manager.get_counters()
        if counters["queued"] >= Config.MAX_TOTAL_URLS:
            logger.info(f"Reached maximum total URLs limit ({Config.MAX_TOTAL_URLS})")
            return

        # Check if domain is related to the university
        is_related = False
        if university_domain in domain:
            is_related = True
        elif is_related_domain(university_domain, domain, university["name"]):
            is_related = True

        if not is_related:
            continue

        # Skip if already visited
        if await state_manager.is_url_visited(link):
            continue

        # Get priority (lower is higher priority)
        priority = get_url_priority(link, university)

        # Add to domain queue
        domain_queue.append((priority, link, depth, university))

    # Queue links
    for priority, link, depth, university in domain_queue:
        await url_queue.put((priority, link, depth, university))
