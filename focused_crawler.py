#!/usr/bin/env python3
"""
Highly focused university application finder.
"""
import asyncio
import aiohttp
import logging
import signal
import time
import json
import re
import sys
from urllib.parse import urlparse, urljoin, parse_qs
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("crawler_new.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Configuration
class Config:
    # List of seed universities to crawl
    SEED_UNIVERSITIES = [
        {"name": "MIT", "base_url": "https://www.mit.edu", "domain": "mit.edu"},
        # {
        #     "name": "Stanford",
        #     "base_url": "https://www.stanford.edu",
        #     "domain": "stanford.edu",
        # },
    ]

    # Crawling settings
    MAX_DEPTH = 6
    REQUEST_TIMEOUT = 10
    REQUEST_DELAY = 1
    MAX_URLS_PER_DOMAIN = 300
    MAX_TOTAL_URLS = 10000
    NUM_WORKERS = 12

    # Application-related keywords
    APPLICATION_KEYWORDS = [
        "apply",
        "application",
        "admission",
        "admissions",
        "undergraduate",
        "freshman",
        "enroll",
        "register",
        "portal",
        "submit",
    ]

    # High-priority URL patterns
    HIGH_PRIORITY_PATTERNS = ["/apply", "/admission", "/admissions", "/undergraduate"]

    # URL patterns to exclude
    EXCLUDED_PATTERNS = [
        r"/news/",
        r"/events/",
        r"/calendar/",
        r"/people/",
        r"/profiles/",
        r"/faculty/",
        r"/staff/",
        r"/directory/",
        r"/search",
        r"/\d{4}/",
        r"/tag/",
        r"/category/",
        r"/archive/",
        r"/page/\d+",
        r"/feed/",
        r"/rss/",
        r"/login",
        r"/accounts/",
    ]

    # File extensions to exclude
    EXCLUDED_EXTENSIONS = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".css",
        ".js",
        ".zip",
        ".tar",
        ".gz",
        ".rar",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
    ]


# Global state
visited_urls = set()
domain_visit_counts = {}
found_applications = []
url_queue = asyncio.Queue()
crawler_running = True
total_urls_visited = 0
total_urls_queued = 0


# Signal handlers for graceful shutdown
def handle_exit(signum, frame):
    global crawler_running
    print("\nReceived exit signal. Shutting down gracefully...")
    crawler_running = False


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


def is_valid_url(url):
    """Check if a URL should be crawled."""
    # Check for invalid schemes
    if not url.startswith(("http://", "https://")):
        return False

    # Parse URL
    parsed = urlparse(url)

    # Check for excluded extensions
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in Config.EXCLUDED_EXTENSIONS):
        return False

    # Check for excluded patterns
    if any(re.search(pattern, path) for pattern in Config.EXCLUDED_PATTERNS):
        return False

    return True


def normalize_url(url):
    """Normalize a URL to avoid duplicates."""
    parsed = urlparse(url)

    # Remove fragment
    parsed = parsed._replace(fragment="")

    # Handle query parameters (remove tracking parameters)
    if parsed.query:
        query_dict = parse_qs(parsed.query)
        # Remove common tracking parameters
        for param in [
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
        ]:
            if param in query_dict:
                del query_dict[param]

        # Rebuild query string
        query_parts = []
        for key in sorted(query_dict.keys()):
            for value in sorted(query_dict[key]):
                query_parts.append(f"{key}={value}")

        new_query = "&".join(query_parts)
        parsed = parsed._replace(query=new_query)

    # Normalize the path (remove trailing slash)
    path = parsed.path
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
        parsed = parsed._replace(path=path)

    return parsed.geturl()


def get_url_priority(url, university):
    """Determine priority for a URL (lower is higher priority)."""
    priority = 10  # Default priority

    # Check for high-priority patterns
    path = urlparse(url).path.lower()
    if any(pattern in path for pattern in Config.HIGH_PRIORITY_PATTERNS):
        priority = 1

    # Check for application keywords in path
    if any(keyword in path for keyword in Config.APPLICATION_KEYWORDS):
        priority = 2

    return priority


def is_application_page(url, html, title=""):
    """Check if a page is likely an application page."""
    if not html:
        return False, []

    reasons = []

    # Check URL for application-related patterns
    path = urlparse(url).path.lower()
    for pattern in Config.HIGH_PRIORITY_PATTERNS:
        if pattern in path:
            reasons.append(f"URL contains pattern '{pattern}'")

    # Check for application keywords in URL
    for keyword in Config.APPLICATION_KEYWORDS:
        if keyword in path:
            reasons.append(f"URL contains keyword '{keyword}'")

    # Check title for application keywords
    if title:
        title_lower = title.lower()
        for keyword in Config.APPLICATION_KEYWORDS:
            if keyword in title_lower:
                reasons.append(f"Title contains keyword '{keyword}'")

    # Check meta description for application keywords
    meta_desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
        html,
        re.IGNORECASE,
    )
    if meta_desc_match:
        meta_desc = meta_desc_match.group(1).lower()
        for keyword in Config.APPLICATION_KEYWORDS:
            if keyword in meta_desc:
                reasons.append(f"Meta description contains keyword '{keyword}'")

    # Check for form with application-related attributes
    form_action_matches = re.findall(
        r'<form[^>]*action=["\'](.*?)["\']', html, re.IGNORECASE
    )
    for action in form_action_matches:
        action_lower = action.lower()
        for keyword in Config.APPLICATION_KEYWORDS:
            if keyword in action_lower:
                reasons.append(f"Form action contains keyword '{keyword}'")

    # Check for application-related buttons or links
    apply_button_match = re.search(
        r"<(a|button)[^>]*>(.*?apply.*?|.*?application.*?|.*?submit.*?)</(a|button)>",
        html,
        re.IGNORECASE,
    )
    if apply_button_match:
        reasons.append("Contains application/submit button or link")

    return len(reasons) > 0, reasons


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

        # Check if valid
        if is_valid_url(normalized):
            links.append(normalized)

    return links


def extract_title(html):
    """Extract page title from HTML."""
    if not html:
        return ""

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
    )
    if title_match:
        return title_match.group(1).strip()
    return ""


async def fetch_url(session, url, depth, university):
    """Fetch a URL and process its content."""
    global crawler_running, total_urls_visited

    if not crawler_running:
        return

    try:
        # Apply politeness delay
        await asyncio.sleep(Config.REQUEST_DELAY)

        # Fetch URL
        async with session.get(
            url, timeout=Config.REQUEST_TIMEOUT, allow_redirects=True
        ) as response:
            if response.status != 200:
                logger.warning(f"Got status {response.status} for {url}")
                return

            total_urls_visited += 1
            html = await response.text()

            # Extract title
            title = extract_title(html)

            # Check if this is an application page
            is_app_page, reasons = is_application_page(url, html, title)

            if is_app_page:
                logger.info(f"Found application page: {url} - {title}")
                logger.info(f"Reasons: {', '.join(reasons)}")

                found_applications.append(
                    {
                        "url": url,
                        "title": title,
                        "university": university["name"],
                        "reasons": reasons,
                        "depth": depth,
                    }
                )

            # Don't extract more links if we've reached max depth
            if depth <= 0:
                return

            # Extract and queue links
            links = extract_links(url, html)
            await queue_links(links, depth - 1, university)

    except aiohttp.ClientError as e:
        logger.error(f"Error fetching {url}: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
    except Exception as e:
        logger.error(f"Unexpected error processing {url}: {e}")


async def queue_links(links, depth, university):
    """Queue links for crawling with domain-specific rate limiting."""
    global total_urls_queued

    if not crawler_running:
        return

    university_domain = university["domain"]
    domain_queue = []

    for link in links:
        if not crawler_running:
            return

        parsed = urlparse(link)
        domain = parsed.netloc

        # Skip if we've reached the max URLs for a domain
        if (
            domain in domain_visit_counts
            and domain_visit_counts[domain] >= Config.MAX_URLS_PER_DOMAIN
        ):
            continue

        # Skip if we've reached the max total URLs
        if total_urls_queued >= Config.MAX_TOTAL_URLS:
            logger.info(f"Reached maximum total URLs limit ({Config.MAX_TOTAL_URLS})")
            return

        # Check if domain is related to the university
        if university_domain not in domain and not is_related_domain(
            university_domain, domain, university["name"]
        ):
            continue

        # Skip if already visited or queued
        if link in visited_urls:
            continue

        # Mark as visited to prevent duplicates
        visited_urls.add(link)

        # Update domain counter
        if domain not in domain_visit_counts:
            domain_visit_counts[domain] = 0
        domain_visit_counts[domain] += 1

        # Get priority
        priority = get_url_priority(link, university)

        # Add to domain queue
        domain_queue.append((priority, link, depth, university))
        total_urls_queued += 1

    # Sort by priority (lower first)
    domain_queue.sort(key=lambda x: x[0])

    # Queue links
    for _, link, depth, university in domain_queue:
        await url_queue.put((link, depth, university))


def is_related_domain(university_domain, url_domain, university_name):
    """Check if a domain is likely related to a university domain."""
    # Direct match
    if university_domain in url_domain:
        return True

    # Common patterns for university-related domains
    related_patterns = [
        r"apply\.",
        r"admission[s]?\.",
        r"undergrad\.",
        r"student\.",
        r"portal\.",
    ]

    for pattern in related_patterns:
        if re.search(pattern, url_domain):
            logger.info(f"Found related domain: {url_domain} for {university_name}")
            return True

    # Check for university name in domain
    university_name_parts = university_name.lower().split()

    # Handle abbreviations (e.g., MIT)
    if len(university_name_parts) > 1:
        abbreviation = "".join(
            word[0] for word in university_name_parts if len(word) > 1
        )
        if len(abbreviation) >= 2 and abbreviation.lower() in url_domain.lower():
            logger.info(
                f"Found related domain by abbreviation: {url_domain} for {university_name}"
            )
            return True

    # Check for parts of university name
    for part in university_name_parts:
        if len(part) > 3 and part.lower() in url_domain.lower():
            logger.info(
                f"Found related domain by name: {url_domain} for {university_name}"
            )
            return True

    return False


async def worker(session, worker_id):
    """Worker to process URLs from the queue."""
    global crawler_running

    logger.info(f"Worker {worker_id} started")

    while crawler_running:
        try:
            # Get URL with timeout to allow for shutdown checks
            try:
                url, depth, university = await asyncio.wait_for(
                    url_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Process URL
            await fetch_url(session, url, depth, university)

            # Mark task as done
            url_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")

    logger.info(f"Worker {worker_id} shutting down")


async def monitor_progress():
    """Monitor and report crawler progress."""
    last_time = time.time()
    last_visited = 0

    while crawler_running:
        try:
            await asyncio.sleep(5)

            current_time = time.time()
            elapsed = current_time - last_time
            visited_delta = total_urls_visited - last_visited
            rate = visited_delta / elapsed if elapsed > 0 else 0

            logger.info(
                f"Progress: {total_urls_visited} URLs visited, {url_queue.qsize()} queued, "
                f"{len(found_applications)} application pages found, {rate:.1f} URLs/sec"
            )

            # Check if queue is empty
            if url_queue.empty() and total_urls_visited > 0:
                logger.info("Queue is empty, crawling complete")
                save_results()
                break

            last_time = current_time
            last_visited = total_urls_visited

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")


def save_results():
    """Save crawler results to JSON file."""
    filename = f"application_pages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, "w") as f:
        json.dump(found_applications, f, indent=2)

    logger.info(f"Results saved to {filename}")

    # Save a summary report
    summary_file = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(summary_file, "w") as f:
        f.write("=== University Application Pages Summary ===\n\n")
        f.write(f"Total URLs visited: {total_urls_visited}\n")
        f.write(f"Total application pages found: {len(found_applications)}\n\n")

        # Group by university
        by_university = {}
        for app in found_applications:
            univ = app["university"]
            if univ not in by_university:
                by_university[univ] = []
            by_university[univ].append(app)

        for univ, apps in by_university.items():
            f.write(f"== {univ}: {len(apps)} application pages ==\n")
            for i, app in enumerate(apps, 1):
                f.write(
                    f"{i}. {app['title']}\n   {app['url']}\n   Reasons: {', '.join(app['reasons'])}\n\n"
                )

    logger.info(f"Summary saved to {summary_file}")

    return filename, summary_file


async def main():
    """Main crawler function."""
    global crawler_running

    logger.info("Starting crawler")

    # Seed the queue
    for university in Config.SEED_UNIVERSITIES:
        await url_queue.put((university["base_url"], Config.MAX_DEPTH, university))
        visited_urls.add(university["base_url"])

        # Add admissions URL directly (if known)
        if university["name"] == "MIT":
            admissions_url = "https://www.mit.edu/admissions-aid"
            await url_queue.put((admissions_url, Config.MAX_DEPTH, university))
            visited_urls.add(admissions_url)
        elif university["name"] == "Stanford":
            admissions_url = "https://www.stanford.edu/admission/"
            await url_queue.put((admissions_url, Config.MAX_DEPTH, university))
            visited_urls.add(admissions_url)

    # Start crawler
    async with aiohttp.ClientSession() as session:
        # Start monitor task
        monitor = asyncio.create_task(monitor_progress())

        # Start workers
        workers = []
        for i in range(Config.NUM_WORKERS):
            worker_task = asyncio.create_task(worker(session, i))
            workers.append(worker_task)

        try:
            # Wait for queue to be empty or max URLs to be reached
            while (
                crawler_running
                and not url_queue.empty()
                and total_urls_visited < Config.MAX_TOTAL_URLS
            ):
                await asyncio.sleep(1)

            logger.info("Finishing up...")

            # Give workers time to finish current tasks
            try:
                await asyncio.wait_for(url_queue.join(), timeout=10)
            except asyncio.TimeoutError:
                pass

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main: {e}")
        finally:
            # Cancel all tasks
            crawler_running = False

            for w in workers:
                w.cancel()

            monitor.cancel()

            # Wait for cancellation to complete
            await asyncio.gather(*workers, monitor, return_exceptions=True)

            # Save results
            if found_applications:
                results_file, summary_file = save_results()
                logger.info(f"Found {len(found_applications)} application pages")
                logger.info(f"Results saved to {results_file} and {summary_file}")
            else:
                logger.info("No application pages found")

    logger.info("Crawler finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected in main thread")
        sys.exit(0)
