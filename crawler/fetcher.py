"""
Modified URL fetching implementation with discovery cutoff and link-per-page limits
"""

import asyncio
import random
import re
import traceback
from urllib.parse import urljoin, urlparse
from collections import defaultdict

import aiohttp
from loguru import logger

from config import Config
from utils.encoding import EncodingHandler
from analysis.page_analyzer import is_application_page, extract_title
from analysis.link_extractor import extract_links
from models.state_manager import state_manager
from utils.url_service import (
    get_url_priority,
    is_related_domain,
    is_valid_domain,
    normalize_url,
    is_valid_url,
)

# Global counter for URLs fetched per domain
domain_fetch_counts = defaultdict(int)
domain_lock = asyncio.Lock()

# Rate limiting per domain - use a default if REQUEST_DELAY is not defined
default_delay = 1.0
domain_rate_limits = defaultdict(
    lambda: getattr(Config, "REQUEST_DELAY", default_delay)
)

# Set of failed domains to skip
failed_domains = set()


class RedirectTracker:
    """
    Tracks redirects to detect and prevent redirect loops
    """

    def __init__(self, max_redirects=5):
        self.redirect_chains = {}  # Maps original_url -> list of redirected URLs
        self.max_redirects = max_redirects
        self.lock = asyncio.Lock()

    async def start_tracking(self, url):
        """Start tracking redirects for a URL"""
        async with self.lock:
            self.redirect_chains[url] = [url]

    async def add_redirect(self, original_url, redirected_url):
        """Add a redirect to the chain"""
        async with self.lock:
            if original_url not in self.redirect_chains:
                self.redirect_chains[original_url] = [original_url]

            # Add the new redirect
            self.redirect_chains[original_url].append(redirected_url)

            # Check for loops
            if self.redirect_chains[original_url].count(redirected_url) > 1:
                logger.warning(
                    f"Redirect loop detected for {original_url} -> {redirected_url}"
                )
                return False

            # Check for maximum redirect chain length
            if len(self.redirect_chains[original_url]) > self.max_redirects:
                logger.warning(
                    f"Maximum redirect chain length ({self.max_redirects}) exceeded for {original_url}"
                )
                return False

            return True

    async def get_redirect_chain(self, url):
        """Get the redirect chain for a URL"""
        async with self.lock:
            return self.redirect_chains.get(url, [url])

    async def is_in_redirect_chain(self, chain_url, target_url):
        """Check if target_url is in the redirect chain of chain_url"""
        async with self.lock:
            chain = self.redirect_chains.get(chain_url, [])
            return target_url in chain


# Create a singleton instance to use throughout the application
redirect_tracker = RedirectTracker()


# Maximum links to extract per page based on priority and depth
async def get_link_limit(depth, is_admission_domain):
    """
    Determine how many links to extract from a page based on depth and domain type.

    Args:
        depth: Current crawl depth
        is_admission_domain: Whether this is an admission-related domain

    Returns:
        int: Maximum number of links to extract
    """
    # Always allow more links from admission domains
    if is_admission_domain:
        if depth > 0:
            return 100  # Good number of links from admission pages
        else:
            return 30  # Fewer links from deeper admission pages

    # For regular domains, limit more strictly based on depth
    max_depth = getattr(Config, "MAX_DEPTH", 12)  # Default to 12 if not defined

    if depth >= max_depth - 1:
        return 10  # Very few links from deep pages
    elif depth >= max_depth - 3:
        return 20  # Few links from somewhat deep pages
    else:
        return 50  # Reasonable number from shallow pages


async def queue_links(links, depth, university, url_queue):
    """Queue links for crawling with improved filtering, limits, and domain verification."""
    global failed_domains

    # Check URL limit before processing
    max_total_urls = getattr(Config, "MAX_TOTAL_URLS", 100000)  # Default if not defined
    if await state_manager.should_enforce_url_limit(max_total_urls):
        return

    university_domain = university["domain"]
    domain_queue = []
    queued_count = 0

    # Calculate link limit
    is_admission_domain = any(
        subdomain in university_domain
        for subdomain in ["admission", "apply", "undergrad"]
    )
    link_limit = await get_link_limit(depth, is_admission_domain)

    # Filter and sort links by priority first
    filtered_links = []
    domain_verified_cache = {}  # Cache for domain verification results

    for link in links:
        # Check if crawler is still running
        if not await state_manager.is_crawler_running():
            return

        # Skip if we've reached the link limit for this page
        if queued_count >= link_limit:
            logger.debug(
                f"Reached link limit ({link_limit}) for current page, skipping remaining links"
            )
            break

        parsed = urlparse(link)
        domain = parsed.netloc.lower()  # Ensure lowercase for consistency

        # Skip already known invalid domains
        if domain in failed_domains:
            continue

        # Verify domain exists using cache to avoid repeated checks
        if domain not in domain_verified_cache:
            domain_verified_cache[domain] = await is_valid_domain(domain)

        if not domain_verified_cache[domain]:
            logger.debug(f"Skipping invalid domain: {domain}")
            continue

        # Skip if we've reached the max URLs for a domain
        domain_counts = await state_manager.get_domain_counts()
        max_urls_per_domain = getattr(
            Config, "MAX_URLS_PER_DOMAIN", 500
        )  # Default if not defined
        if domain in domain_counts and domain_counts[domain] >= max_urls_per_domain:
            continue

        # Skip if we've reached the max total URLs
        counters = await state_manager.get_counters()
        if counters["queued"] >= max_total_urls:
            logger.info(f"Reached maximum total URLs limit ({max_total_urls})")
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

        # Skip if not a valid URL based on patterns
        if not is_valid_url(link):
            continue

        # Get priority (lower is higher priority)
        priority = get_url_priority(link, university)

        # Add to domain queue
        filtered_links.append((priority, link, depth, university))

    # Sort by priority (lower numbers first)
    filtered_links.sort(key=lambda x: x[0])

    # Only queue the top links based on our limit
    for priority, link, depth, university in filtered_links[:link_limit]:
        await url_queue.put((priority, link, depth, university))
        queued_count += 1

    if queued_count > 0:
        logger.debug(f"Queued {queued_count} links (out of {len(links)} discovered)")

    return queued_count


async def fetch_url(session, url, depth, university, url_queue):
    """Fetch a URL and process its content with improved discovery management."""
    # First check if the crawler is still running
    if not await state_manager.is_crawler_running():
        return

    # Normalize URL to handle Unicode
    normalized_url = normalize_url(url)
    if normalized_url != url:
        logger.debug(f"Normalized URL: {url} -> {normalized_url}")
        url = normalized_url

    # Start tracking redirects for this URL
    await redirect_tracker.start_tracking(url)

    try:
        # Get domain for rate limiting
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # Track domain fetch counts and apply adaptive rate limiting
        async with domain_lock:
            domain_fetch_counts[domain] += 1

            # Apply dynamic rate limiting based on domain fetch count
            # More requests to a domain = longer delays
            default_delay = getattr(Config, "REQUEST_DELAY", 1.0)
            if domain_fetch_counts[domain] > 50:
                domain_rate_limits[domain] = max(
                    default_delay * 2, domain_rate_limits[domain]
                )
            if domain_fetch_counts[domain] > 100:
                domain_rate_limits[domain] = max(
                    default_delay * 3, domain_rate_limits[domain]
                )

            # Apply the rate limit delay
            delay = domain_rate_limits[domain]

        # Apply politeness delay with domain-specific rate
        await asyncio.sleep(delay)

        # Log when fetching admission-related domains for debugging
        is_admission_domain = False
        if (
            "admission" in domain
            or "apply" in domain
            or "undergrad" in domain
            or any(p in path for p in ["/apply", "/admission", "/admissions"])
        ):
            is_admission_domain = True
            logger.info(f"Fetching admission-related URL: {url} (depth {depth})")

        # Set up headers
        headers = {
            "User-Agent": getattr(
                Config, "USER_AGENT", "University-Application-Crawler/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "DNT": "1",
        }

        # Use rotating user agents if configured
        if (
            getattr(Config, "USER_AGENT_ROTATION", False)
            and hasattr(Config, "USER_AGENTS")
            and Config.USER_AGENTS
        ):
            headers["User-Agent"] = random.choice(Config.USER_AGENTS)

        # Fetch URL with headers and timeout - use default if REQUEST_TIMEOUT not defined
        timeout_value = getattr(Config, "REQUEST_TIMEOUT", 15)
        async with session.get(
            url, timeout=timeout_value, allow_redirects=True, headers=headers
        ) as response:
            if response.status != 200:
                logger.warning(f"Got status {response.status} for {url}")
                return

            # Track any redirects that occurred
            if str(response.url) != url:
                logger.info(f"Redirected: {url} -> {response.url}")

                # Normalize the final URL
                final_url = normalize_url(str(response.url))

                # Add to redirect chain
                if not await redirect_tracker.add_redirect(url, final_url):
                    logger.warning(f"Skipping URL due to redirect issues: {url}")
                    return

                # Update the URL to the final redirected URL
                url = final_url

            # Increment visited counter and track domain
            await state_manager.increment_visited_counter()
            await state_manager.increment_domain_count(domain)

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

            # Handle depth management and discovery cutoff
            current_depth = depth
            extend_depth = False

            # Check if we're on an admission-related domain to increase depth
            if is_admission_domain:
                # Add to our set of admission domains
                await state_manager.add_admission_domain(domain)

                # Look for specific application links if we're in an admission domain
                apply_links = await find_critical_application_links(url, html)

                # Process these critical links with highest priority (depth doesn't matter)
                for link in apply_links:
                    # Check if this is in a redirect chain to prevent loops
                    if await redirect_tracker.is_in_redirect_chain(url, link):
                        logger.warning(
                            f"Skipping link {link} - already in redirect chain"
                        )
                        continue

                    # Use a high priority value (0) for critical application links
                    max_depth = getattr(Config, "MAX_DEPTH", 12)
                    await url_queue.put((0, link, max_depth, university))

                # Extend depth for admission domains
                extend_depth = True

            # Discovery cutoff for regular domains
            if not extend_depth and depth <= 0:
                logger.debug(f"Reached depth limit for regular domain: {url}")
                return

            # Special handling for admission domains
            if extend_depth:
                max_admission_depth = getattr(Config, "MAX_ADMISSION_DEPTH", 15)
                if depth <= 0 and depth > -max_admission_depth:
                    logger.info(f"Allowing extended depth for admission URL: {url}")
                    # Continue with negative depth to track extended crawling
                    current_depth = -1  # Start extended depth crawling
                elif depth < 0 and depth <= -max_admission_depth:
                    logger.debug(
                        f"Reached extended depth limit for admission domain: {url}"
                    )
                    return

            # Check URL limit again before extracting links
            max_total_urls = getattr(Config, "MAX_TOTAL_URLS", 100000)
            if await state_manager.should_enforce_url_limit(max_total_urls):
                return

            # Extract and queue links with limits
            links = extract_links(url, html)
            await queue_links(links, current_depth - 1, university, url_queue)

    except aiohttp.ClientError as e:
        logger.error(f"Error fetching {url}: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")

        # Increase delay for this domain on timeout
        async with domain_lock:
            domain_rate_limits[domain] = min(domain_rate_limits[domain] * 1.5, 5.0)
            logger.info(
                f"Increased rate limit for domain {domain} to {domain_rate_limits[domain]}s"
            )
    except aiohttp.ServerDisconnectedError:
        logger.error(f"Server disconnected while fetching {url}")
        # Increase delay for this domain on disconnect
        async with domain_lock:
            domain_rate_limits[domain] = min(domain_rate_limits[domain] * 1.5, 5.0)
    except Exception as e:
        logger.error(f"Unexpected error processing {url}: {e}")

        logger.debug(f"Exception traceback: {traceback.format_exc()}")


async def find_critical_application_links(url, html):
    """Find critical application links in admission-related pages."""
    apply_links = []
    apply_patterns = [
        r'<a[^>]*href=["\'](.*?apply.*?first-year.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?freshman.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?undergraduate.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply.*?transfer.*?)["\']',
        r'<a[^>]*href=["\'](.*?admission.*?apply.*?)["\']',
        r'<a[^>]*href=["\'](.*?admission.*?first-year.*?)["\']',
        r'<a[^>]*href=["\'](.*?admission.*?freshman.*?)["\']',
        r'<a[^>]*href=["\'](.*?portal.*?applicant.*?)["\']',
        r'<a[^>]*href=["\'](.*?apply-now.*?)["\']',
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
