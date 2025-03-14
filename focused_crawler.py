import asyncio
import random
import aiohttp
import signal
import time
import json
import re
import sys
import os
from urllib.parse import urlparse, urljoin, parse_qs
from datetime import datetime
from loguru import logger
import openai

# Database functions imports
database_available = False
try:
    from database import init_database, save_metrics_to_db, get_aggregated_metrics

    database_available = True
except ImportError:
    logger.warning(
        "Could not import database functions. Metrics will not be saved to database."
    )
    database_available = False

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("ERROR: OPENAI_API_KEY environment variable not set")
    sys.exit(1)

# Configure Loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
)
logger.add(
    "crawler.log",
    rotation="10 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
)


# Global tracker for API metrics
api_metrics = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
    "pages_evaluated": 0,
}

# Lock for API metrics
api_metrics_lock = asyncio.Lock()


# Configuration
class Config:
    # List of seed universities to crawl
    SEED_UNIVERSITIES = [
        # {"name": "MIT", "base_url": "https://www.mit.edu", "domain": "mit.edu"},
        {
            "name": "Stanford",
            "base_url": "https://www.stanford.edu",
            "domain": "stanford.edu",
        },
    ]

    # Known admission subdomains (to add as seeds)
    ADMISSION_SUBDOMAINS = {
        # "mit.edu": ["admissions.mit.edu", "apply.mit.edu"],
        # "stanford.edu": [
        #     "admission.stanford.edu",
        #     "apply.stanford.edu",
        #     "admissions.stanford.edu",
        #     "undergrad.stanford.edu",
        # ],
    }

    # Crawling settings
    MAX_DEPTH = 12  # Increased from 7 to ensure we reach deeper pages
    MAX_ADMISSION_DEPTH = 15  # Special deeper crawl for admission-related domains
    REQUEST_TIMEOUT = 15  # Increased from 10 to handle slower sites
    REQUEST_DELAY = 1
    MAX_URLS_PER_DOMAIN = 600  # Increased from 300 to explore more
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
        "first-year",
        "transfer",
        "applicant",
        "prospective",
    ]

    # Direct application form indicators
    APPLICATION_FORM_INDICATORS = [
        "start application",
        "begin application",
        "submit application",
        "create account",
        "application form",
        "apply now",
        "start your application",
        "application status",
        "application portal",
        "common app",
        "common application",
        "coalition app",
    ]

    # High-priority URL patterns - more specific patterns first
    HIGH_PRIORITY_PATTERNS = [
        "/apply/first-year",
        "/apply/transfer",
        "/apply/freshman",
        "/apply/undergraduate",
        "/apply/online",
        "/admission/apply",
        "/admission/application",
        "/admission/first-year",
        "/admission/undergraduate",
        "/admissions/apply",
        "/apply",
        "/admission",
        "/admissions",
        "/undergraduate",
    ]

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
        r"/alumni/",
        r"/giving/",
        r"/support/",
        r"/donate/",
        r"/covid",
        r"/research/",
        r"/athletics/",
        r"/sports/",
        r"/about/",
        r"/contact/",
        r"/privacy/",
        r"/terms/",
        r"/campus-map/",
        r"/campus-tour/",
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

    # OpenAI settings
    MODEL_NAME = "gpt-4o-mini"
    MAX_EVAL_BATCH = 10  # Evaluate this many URLs in one batch
    MAX_CONCURRENT_API_CALLS = 5  # Maximum concurrent API calls

    # Database settings
    USE_SQLITE = True

    # User agent settings
    USER_AGENT = "University-Application-Crawler/1.0 (contact: ghoulbites777@gmail.com)"
    USER_AGENT_ROTATION = True
    USER_AGENTS = [
        "University-Application-Crawler/1.0 (contact: ghoulbites777@gmail.com)",
        "UniversityApplicationFinder/1.0 (contact: ghoulbites777@gmail.com)",
        "EducationalCrawler/1.0 (contact: ghoulbites777@gmail.com)",
    ]


# Global state
visited_urls = set()
domain_visit_counts = {}
found_applications = []
evaluated_applications = []
url_queue = asyncio.Queue()
crawler_running = True
total_urls_visited = 0
total_urls_queued = 0

# Keep track of admission-related domains for higher depth crawling
admission_related_domains = set()

# API rate limiting
api_semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_API_CALLS)


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
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # Highest priority: Look for exact application paths
    if any(
        pattern in path
        for pattern in ["/apply/first-year", "/admission/apply", "/apply/undergraduate"]
    ):
        return 0

    # Second highest: Admission subdomains with application paths
    if ("admission" in domain or "apply" in domain or "undergrad" in domain) and any(
        p in path
        for p in ["/apply", "/admission", "/application", "/portal", "/first-year"]
    ):
        return 1

    # Third highest: General admission subdomains
    if any(x in domain for x in ["admission", "apply", "undergrad", "freshman"]):
        return 2

    # Fourth highest: Important paths on any domain
    for i, pattern in enumerate(Config.HIGH_PRIORITY_PATTERNS):
        if pattern in path:
            return 3 + (i * 0.1)  # Small increments to maintain ordering of patterns

    # Fifth highest: URLs with application keywords in path
    if any(keyword in path for keyword in Config.APPLICATION_KEYWORDS):
        return 5

    # Default priority - consider depth from homepage
    segments = [s for s in path.split("/") if s]
    return 10 + len(segments)


def is_application_page(url, html, title=""):
    """Check if a page is likely an application page."""
    if not html:
        return False, []

    reasons = []
    score = 0  # Track a confidence score

    # Parse URL components
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # Domain-level checks (subdomain indicates strong likelihood)
    if any(x in domain for x in ["admission", "apply", "applicant", "undergrad"]):
        reasons.append(f"URL subdomain suggests application page: {domain}")
        score += 3

    # Path-level checks - give higher weight to specific patterns
    for pattern in Config.HIGH_PRIORITY_PATTERNS:
        if pattern in path:
            reasons.append(f"URL contains high-priority pattern '{pattern}'")
            score += 2

    # Check for application keywords in URL
    for keyword in Config.APPLICATION_KEYWORDS:
        if keyword in path:
            reasons.append(f"URL contains keyword '{keyword}'")
            score += 1

    # Check title for application keywords - strong indicator
    if title:
        title_lower = title.lower()
        for keyword in Config.APPLICATION_KEYWORDS:
            if keyword in title_lower:
                reasons.append(f"Title contains keyword '{keyword}'")
                score += 2

        # Check for direct application indicators in title
        for indicator in Config.APPLICATION_FORM_INDICATORS:
            if indicator in title_lower:
                reasons.append(
                    f"Title contains application form indicator '{indicator}'"
                )
                score += 3

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
                score += 1

        # Check for direct application indicators in meta description
        for indicator in Config.APPLICATION_FORM_INDICATORS:
            if indicator in meta_desc:
                reasons.append(
                    f"Meta description contains application form indicator '{indicator}'"
                )
                score += 2

    # Check for form with application-related attributes
    form_action_matches = re.findall(
        r'<form[^>]*action=["\'](.*?)["\']', html, re.IGNORECASE
    )
    for action in form_action_matches:
        action_lower = action.lower()
        for keyword in Config.APPLICATION_KEYWORDS:
            if keyword in action_lower:
                reasons.append(f"Form action contains keyword '{keyword}'")
                score += 3

    # Check for application-related buttons or links
    for indicator in Config.APPLICATION_FORM_INDICATORS:
        pattern = re.escape(indicator)
        if re.search(
            f"<(a|button)[^>]*>(.*?{pattern}.*?)</(a|button)>",
            html,
            re.IGNORECASE,
        ):
            reasons.append(f"Contains application button/link with text '{indicator}'")
            score += 4

    # Check for Common App/Coalition App references (strong indicators)
    if re.search(
        r"common\s*app(lication)?|coalition\s*app(lication)?", html, re.IGNORECASE
    ):
        reasons.append("Page references Common App or Coalition App")
        score += 4

    # Check for login/authentication elements specifically for applicants
    if re.search(
        r"applicant\s*login|application\s*login|application\s*portal",
        html,
        re.IGNORECASE,
    ):
        reasons.append("Page contains applicant login elements")
        score += 4

    # Return based on both criteria count and confidence score
    return score >= 3, reasons


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
    global crawler_running, total_urls_visited, admission_related_domains

    if not crawler_running:
        return

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

        # Fetch URL
        async with session.get(
            url, timeout=Config.REQUEST_TIMEOUT, allow_redirects=True, headers=headers
        ) as response:
            if response.status != 200:
                logger.warning(f"Got status {response.status} for {url}")
                return

            total_urls_visited += 1

            # Log the final URL after any redirects
            if response.url != url:
                logger.info(f"Redirected: {url} -> {response.url}")

            html = await response.text()

            # Extract title
            title = extract_title(html)

            # Check if this is an application page
            is_app_page, reasons = is_application_page(url, html, title)

            if is_app_page:
                logger.success(f"Found application page: {url} - {title}")
                logger.info(f"Reasons: {', '.join(reasons)}")

                found_applications.append(
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
                admission_related_domains.add(domain)

                # Look for specific application links if we're in an admission domain
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

                        if is_valid_url(normalized) and normalized not in visited_urls:
                            logger.info(
                                f"Found critical application link: {normalized}"
                            )
                            apply_links.append(normalized)

                # Process these critical links with highest priority (depth doesn't matter)
                for link in apply_links:
                    visited_urls.add(link)
                    await url_queue.put(
                        (link, Config.MAX_DEPTH, university)
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
        is_related = False
        if university_domain in domain:
            is_related = True
        elif is_related_domain(university_domain, domain, university["name"]):
            is_related = True

        if not is_related:
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
    url_domain_lower = url_domain.lower()

    # Direct match
    if university_domain in url_domain_lower:
        return True

    # Special handling for admission-related subdomains (highest priority)
    if any(
        term in url_domain_lower
        for term in ["admission", "apply", "undergrad", "applicant"]
    ):
        university_root = university_domain.split(".")[
            -2
        ]  # e.g., 'stanford' from 'stanford.edu'
        if university_root in url_domain_lower:
            logger.info(
                f"Found critical admission domain: {url_domain} for {university_name}"
            )
            return True

    # Common patterns for university-related domains
    related_patterns = [
        r"apply\.",
        r"admission[s]?\.",
        r"undergrad\.",
        r"student\.",
        r"portal\.",
        r"applicant\.",
        r"freshman\.",
        r"myapp\.",
        r"commonapp\.",
    ]

    for pattern in related_patterns:
        if re.search(pattern, url_domain_lower):
            logger.info(f"Found related domain: {url_domain} for {university_name}")
            return True

    # Check for university name in domain
    university_name_parts = university_name.lower().split()

    # Handle abbreviations (e.g., MIT)
    if len(university_name_parts) > 1:
        abbreviation = "".join(
            word[0] for word in university_name_parts if len(word) > 1
        )
        if len(abbreviation) >= 2 and abbreviation.lower() in url_domain_lower:
            logger.info(
                f"Found related domain by abbreviation: {url_domain} for {university_name}"
            )
            return True

    # Check for parts of university name
    for part in university_name_parts:
        if len(part) > 3 and part.lower() in url_domain_lower:
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


# Add after evaluating and finding admission domains
async def explore_specific_application_paths():
    """Directly check common application paths on found admission domains."""
    if not admission_related_domains:
        return

    logger.info(
        f"Exploring specific application paths on {len(admission_related_domains)} admission domains"
    )

    async with aiohttp.ClientSession() as session:
        for domain in admission_related_domains:
            # Common application paths to check directly
            specific_paths = [
                "/apply",
                "/apply/",  # With trailing slash
                "/apply/first-year",
                "/apply/first-year/",  # With trailing slash
                "/apply/freshman",
                "/apply/undergraduate",
                "/application",
                "/admission/apply",
                "/admission/first-year",
                "/admission/freshman",
            ]

            for path in specific_paths:
                full_url = f"https://{domain}{path}"
                if full_url in visited_urls:
                    continue

                logger.info(f"Directly checking potential application path: {full_url}")
                try:
                    async with session.get(
                        full_url, timeout=Config.REQUEST_TIMEOUT
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            title = extract_title(html)

                            # Skip 404 pages even if they return 200 status
                            if "not found" in title.lower():
                                logger.warning(
                                    f"Skipping 404 page: {full_url} - {title}"
                                )
                                continue

                            # Check if this is an application page
                            is_app_page, reasons = is_application_page(
                                full_url, html, title
                            )
                            if is_app_page:
                                logger.success(
                                    f"Found direct application path: {full_url} - {title}"
                                )
                                # Add to found applications
                                for university in Config.SEED_UNIVERSITIES:
                                    if university["domain"] in domain:
                                        found_applications.append(
                                            {
                                                "url": full_url,
                                                "title": title,
                                                "university": university["name"],
                                                "reasons": reasons,
                                                "depth": 0,
                                                "html_snippet": html[:5000],
                                            }
                                        )
                                        break

                            # If we find a valid /apply path, recursively check its subpaths
                            if (
                                "/apply" in path or path.endswith("/apply/")
                            ) and "not found" not in title.lower():
                                await check_subpaths(
                                    full_url,
                                    university_name=next(
                                        u["name"]
                                        for u in Config.SEED_UNIVERSITIES
                                        if u["domain"] in domain
                                    ),
                                )

                except Exception as e:
                    logger.error(f"Error checking direct path {full_url}: {e}")


async def check_subpaths(base_url, university_name):
    """Recursively check subpaths of a valid application URL."""
    logger.info(f"Checking subpaths of {base_url}")

    # Define application subpaths to check
    subpaths = [
        "first-year",
        "first-year/",
        "freshman",
        "freshman/",
        "undergraduate",
        "undergraduate/",
        "transfer",
        "transfer/",
    ]

    async with aiohttp.ClientSession() as session:
        for subpath in subpaths:
            if base_url.endswith("/"):
                full_url = f"{base_url}{subpath}"
            else:
                full_url = f"{base_url}/{subpath}"

            if full_url in visited_urls:
                continue

            visited_urls.add(full_url)
            logger.info(f"Checking application subpath: {full_url}")
            try:
                async with session.get(
                    full_url, timeout=Config.REQUEST_TIMEOUT
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        title = extract_title(html)

                        # Skip 404 pages
                        if (
                            "not found" in title.lower()
                            or "page not found" in html.lower()
                        ):
                            logger.warning(f"Skipping 404 page: {full_url} - {title}")
                            continue

                        # Check if this is an application page
                        is_app_page, reasons = is_application_page(
                            full_url, html, title
                        )
                        if is_app_page:
                            logger.success(
                                f"Found application subpath: {full_url} - {title}"
                            )
                            # Add to found applications
                            found_applications.append(
                                {
                                    "url": full_url,
                                    "title": title,
                                    "university": university_name,
                                    "reasons": reasons,
                                    "depth": 0,
                                    "html_snippet": html[:5000],
                                }
                            )

                        # Also check for specific keywords in the HTML that might indicate application content
                        if any(
                            term in html.lower()
                            for term in [
                                "application form",
                                "common app",
                                "apply now",
                                "application deadline",
                            ]
                        ):
                            logger.success(
                                f"Found application-related content: {full_url} - {title}"
                            )
                            # Add to found applications if not already added
                            if not is_app_page:
                                found_applications.append(
                                    {
                                        "url": full_url,
                                        "title": title,
                                        "university": university_name,
                                        "reasons": [
                                            "Contains application-related content"
                                        ],
                                        "depth": 0,
                                        "html_snippet": html[:5000],
                                    }
                                )

                        # Extract links from this page to find more application pages
                        if "/apply/" in full_url or "/application/" in full_url:
                            links = extract_links(full_url, html)
                            for link in links:
                                if any(
                                    term in link.lower()
                                    for term in [
                                        "/apply/",
                                        "/first-year/",
                                        "/freshman/",
                                        "/application/",
                                        "/submit/",
                                    ]
                                ):
                                    if link not in visited_urls:
                                        visited_urls.add(link)
                                        logger.info(
                                            f"Found additional application link: {link}"
                                        )
                                        try:
                                            async with session.get(
                                                link, timeout=Config.REQUEST_TIMEOUT
                                            ) as link_response:
                                                if link_response.status == 200:
                                                    link_html = (
                                                        await link_response.text()
                                                    )
                                                    link_title = extract_title(
                                                        link_html
                                                    )
                                                    if (
                                                        "not found"
                                                        not in link_title.lower()
                                                    ):
                                                        (
                                                            is_link_app_page,
                                                            link_reasons,
                                                        ) = is_application_page(
                                                            link, link_html, link_title
                                                        )
                                                        if is_link_app_page:
                                                            logger.success(
                                                                f"Found linked application page: {link} - {link_title}"
                                                            )
                                                            found_applications.append(
                                                                {
                                                                    "url": link,
                                                                    "title": link_title,
                                                                    "university": university_name,
                                                                    "reasons": link_reasons,
                                                                    "depth": 0,
                                                                    "html_snippet": link_html[
                                                                        :5000
                                                                    ],
                                                                }
                                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Error checking application link {link}: {e}"
                                            )
            except Exception as e:
                logger.error(f"Error checking subpath {full_url}: {e}")


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

            # Log admission domains we've found
            if admission_related_domains:
                logger.info(
                    f"Found admission domains: {', '.join(admission_related_domains)}"
                )

            # Check if queue is empty
            if url_queue.empty() and total_urls_visited > 0:
                logger.info("Queue is empty, crawling complete")
                break

            last_time = current_time
            last_visited = total_urls_visited

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")


async def evaluate_application_page(app_page):
    """Use GPT-4o-mini to evaluate if a page is truly an application page."""
    global api_metrics, api_metrics_lock

    try:
        # Use semaphore to limit concurrent API calls
        async with api_semaphore:
            prompt = f"""
            Analyze this university webpage and determine if it is an actual application page or portal where students can apply to the university.

            University: {app_page['university']}
            Page Title: {app_page['title']}
            URL: {app_page['url']}
            Detected Reasons: {', '.join(app_page['reasons'])}

            Please determine:
            1. Is this a direct application page or portal where students can start/submit an application?
            2. Is this a page with information about how to apply but not an actual application?
            3. Is this an unrelated page that was incorrectly flagged?

            Focus on whether students can actually BEGIN or SUBMIT an application on this page.
            Look for forms, "Apply Now" buttons that lead directly to applications, links or buttons to outside domains and services (Common App in the US, UCAS in the UK, UniAssist in Germany, etc.), login portals specifically for applicants, etc.

            Your task:
            - Respond with TRUE if this is definitely an actual application page or portal where students can apply
            - Respond with FALSE if this is just information or unrelated
            - Then provide a brief explanation for your decision
            
            Format your response like this:
            RESULT: TRUE/FALSE
            EXPLANATION: Your explanation here
            """

            # Use the synchronous API but run it in a separate thread to keep things async
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=Config.MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at analyzing university websites and identifying actual application pages versus informational pages.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                ),
            )

            # Track metrics with async lock to prevent race conditions
            async with api_metrics_lock:
                api_metrics["prompt_tokens"] += response.usage.prompt_tokens
                api_metrics["completion_tokens"] += response.usage.completion_tokens
                api_metrics["total_tokens"] += response.usage.total_tokens
                api_metrics["pages_evaluated"] += 1

                # Calculate cost based on model pricing - adjust rates as needed
                rate_per_1k_input = 0.00015  # Rate for GPT-4o-mini prompt tokens
                rate_per_1k_completion = (
                    0.0006  # Rate for GPT-4o-mini completion tokens
                )
                rate_per_1k_cached_input = (
                    0.000075  # Rate for GPT-4o-mini cached prompt tokens
                )

                page_cost = (
                    (response.usage.prompt_tokens / 1000) * rate_per_1k_input
                    + (response.usage.prompt_tokens_details.cached_tokens / 1000)
                    * rate_per_1k_cached_input
                    + (response.usage.completion_tokens / 1000) * rate_per_1k_completion
                )
                api_metrics["estimated_cost_usd"] += page_cost

            result_text = response.choices[0].message.content.strip()

            # Parse the response
            result_match = re.search(
                r"RESULT:\s*(TRUE|FALSE)", result_text, re.IGNORECASE
            )
            explanation_match = re.search(
                r"EXPLANATION:\s*(.*)", result_text, re.DOTALL
            )

            is_actual_application = False
            explanation = "Could not evaluate"

            if result_match:
                is_actual_application = result_match.group(1).upper() == "TRUE"

            if explanation_match:
                explanation = explanation_match.group(1).strip()

            # Create evaluated entry
            evaluated_entry = app_page.copy()
            evaluated_entry.pop(
                "html_snippet", None
            )  # Remove HTML snippet to save space
            evaluated_entry["is_actual_application"] = is_actual_application
            evaluated_entry["ai_evaluation"] = explanation

            log_prefix = (
                "✅ ACTUAL APPLICATION"
                if is_actual_application
                else "❌ NOT APPLICATION"
            )
            logger.info(f"Evaluated {app_page['url']}: {log_prefix}")

            return evaluated_entry

    except Exception as e:
        logger.error(f"Error evaluating {app_page['url']}: {e}")

        # Return with error message
        evaluated_entry = app_page.copy()
        evaluated_entry.pop("html_snippet", None)
        evaluated_entry["is_actual_application"] = False
        evaluated_entry["ai_evaluation"] = f"Error during evaluation: {str(e)}"

        return evaluated_entry


async def evaluate_all_applications():
    """Evaluate all found application pages using GPT-4o-mini."""
    if not found_applications:
        logger.warning("No application pages to evaluate")
        return []

    logger.info(
        f"Evaluating {len(found_applications)} application pages with {Config.MODEL_NAME}..."
    )

    # Evaluate in batches to avoid overwhelming the API
    results = []
    batch_size = Config.MAX_EVAL_BATCH

    for i in range(0, len(found_applications), batch_size):
        batch = found_applications[i : i + batch_size]
        logger.info(
            f"Evaluating batch {i//batch_size + 1} of {(len(found_applications)-1)//batch_size + 1} ({len(batch)} pages)"
        )

        # Process the batch concurrently
        batch_results = await asyncio.gather(
            *[evaluate_application_page(app) for app in batch]
        )
        results.extend(batch_results)

        # Brief pause between batches
        if i + batch_size < len(found_applications):
            await asyncio.sleep(1)

    return results


def save_results(evaluated=None):
    """Save crawler results to JSON files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save original results
    original_filename = f"application_pages_{timestamp}.json"
    with open(original_filename, "w") as f:
        json.dump(found_applications, f, indent=2)

    logger.info(f"Original results saved to {original_filename}")

    # Save evaluated results if available
    if evaluated:
        evaluated_filename = f"evaluated_applications_{timestamp}.json"
        with open(evaluated_filename, "w") as f:
            json.dump(evaluated, f, indent=2)

        logger.info(f"Evaluated results saved to {evaluated_filename}")

        # Count actual application pages
        actual_count = sum(
            1 for app in evaluated if app.get("is_actual_application", False)
        )

        # Get unique universities visited
        universities_visited = list(set(app["university"] for app in evaluated))

        # Save a summary report
        summary_file = f"summary_{timestamp}.txt"

        with open(summary_file, "w") as f:
            # We'll add API metrics at the very top in the main function
            # This section creates the main summary content

            f.write("=== University Application Pages Summary ===\n\n")
            f.write(f"Universities Visited: {', '.join(universities_visited)}\n")
            f.write(f"Total URLs visited: {total_urls_visited}\n")
            f.write(f"Total application pages found: {len(found_applications)}\n")
            f.write(f"Actual application pages (AI evaluated): {actual_count}\n\n")

            # Group by university
            by_university = {}
            for app in evaluated:
                univ = app["university"]
                if univ not in by_university:
                    by_university[univ] = []
                by_university[univ].append(app)

            for univ, apps in by_university.items():
                f.write(f"== {univ}: {len(apps)} application pages ==\n")

                # First list actual application pages
                f.write("\n--- ACTUAL APPLICATION PAGES ---\n")
                actual_apps = [
                    app for app in apps if app.get("is_actual_application", False)
                ]
                for i, app in enumerate(actual_apps, 1):
                    f.write(
                        f"{i}. {app['title']}\n   {app['url']}\n   Evaluation: {app['ai_evaluation']}\n\n"
                    )

                # Then list information/other pages
                f.write("\n--- INFORMATION/OTHER PAGES ---\n")
                info_apps = [
                    app for app in apps if not app.get("is_actual_application", False)
                ]
                for i, app in enumerate(info_apps, 1):
                    f.write(
                        f"{i}. {app['title']}\n   {app['url']}\n   Evaluation: {app['ai_evaluation']}\n\n"
                    )

        logger.info(f"Summary saved to {summary_file}")
        return original_filename, evaluated_filename, summary_file

    return original_filename, None, None


async def main():
    """Main crawler function."""
    global crawler_running, api_metrics, database_available

    logger.info("Starting crawler")

    # Generate a unique run ID for this crawl
    run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Initialize the database if enabled
    if Config.USE_SQLITE and database_available:
        try:
            await init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            # Continue with reduced functionality
            database_available = False

    # Reset metrics for this run
    api_metrics = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "pages_evaluated": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "university": (
            Config.SEED_UNIVERSITIES[0]["name"]
            if Config.SEED_UNIVERSITIES
            else "Unknown"
        ),
        "model": Config.MODEL_NAME,
    }

    # Seed the queue with university home pages
    for university in Config.SEED_UNIVERSITIES:
        # Add the main university domain
        await url_queue.put((university["base_url"], Config.MAX_DEPTH, university))
        visited_urls.add(university["base_url"])

        # Add known admission subdomains as seeds
        university_domain = university["domain"]
        if university_domain in Config.ADMISSION_SUBDOMAINS:
            for subdomain in Config.ADMISSION_SUBDOMAINS[university_domain]:
                admission_url = f"https://{subdomain}/"
                logger.info(f"Adding admission seed URL: {admission_url}")
                await url_queue.put((admission_url, Config.MAX_DEPTH, university))
                visited_urls.add(admission_url)

                # Add common application paths to these admission domains
                for path in [
                    "/apply",
                    "/first-year",
                    "/apply/first-year",
                    "/undergraduate",
                    "/under-graduate",
                    "/freshman",
                    "/undergrad",
                    "/admissions",
                    "/application",
                    "/portal",
                    "/enroll",
                    "/register",
                    "/prospective",
                    "/admission",
                ]:
                    path_url = f"https://{subdomain}{path}"
                    logger.info(f"Adding admission path URL: {path_url}")
                    await url_queue.put((path_url, Config.MAX_DEPTH, university))
                    visited_urls.add(path_url)

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

            if admission_related_domains:
                logger.info(
                    "Exploring specific application paths on admission domains..."
                )
                await explore_specific_application_paths()

            # Evaluate application pages with GPT-4o-mini
            summary_file = None
            evaluated_results = []
            if found_applications:
                logger.info(
                    f"Found {len(found_applications)} potential application pages"
                )

                try:
                    evaluated_results = await evaluate_all_applications()

                    if evaluated_results:
                        actual_count = sum(
                            1
                            for app in evaluated_results
                            if app.get("is_actual_application", False)
                        )
                        logger.success(
                            f"Identified {actual_count} actual application pages out of {len(evaluated_results)} candidates"
                        )
                    else:
                        logger.warning("No evaluation results were returned")

                    # Save results
                    try:
                        original_file, evaluated_file, summary_file = save_results(
                            evaluated_results
                        )
                        logger.success(
                            f"Results saved to {original_file}, {evaluated_file if evaluated_file else 'N/A'}, and {summary_file if summary_file else 'N/A'}"
                        )
                    except Exception as file_error:
                        logger.error(f"Error saving results: {file_error}")
                        # Try to save original results at least
                        original_file = save_results()
                        logger.info(f"Original results saved to {original_file}")

                except Exception as eval_error:
                    logger.error(f"Error during evaluation: {eval_error}")
                    # Try to salvage what we can
                    try:
                        original_file = save_results()
                        logger.info(
                            f"Original results saved to {original_file} despite evaluation failure"
                        )
                    except Exception as save_error:
                        logger.error(
                            f"Failed to save even original results: {save_error}"
                        )
            else:
                logger.warning("No application pages found")

            # After evaluation, save the metrics
            if found_applications and Config.USE_SQLITE and database_available:
                try:
                    # Save metrics to the database
                    await save_metrics_to_db(api_metrics, run_id)
                    logger.info(f"Saved API metrics to database for run {run_id}")

                    # Get historical metrics for the summary
                    try:
                        historical_metrics = await get_aggregated_metrics("month")
                    except Exception as e:
                        logger.error(f"Failed to get historical metrics: {e}")
                        historical_metrics = {
                            "total_runs": 0,
                            "total_pages": 0,
                            "total_tokens": 0,
                            "total_cost": 0.0,
                        }

                    # Ensure we have a valid summary file
                    if summary_file:
                        # Create a temporary file with metrics
                        temp_metrics_file = f"temp_metrics_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
                        try:
                            with open(temp_metrics_file, "w") as f:
                                f.write("=== API Usage Metrics ===\n\n")
                                f.write(
                                    f"Model: {api_metrics.get('model', Config.MODEL_NAME)}\n"
                                )
                                f.write(
                                    f"Pages evaluated: {api_metrics.get('pages_evaluated', 0)}\n"
                                )
                                f.write(
                                    f"Prompt tokens: {api_metrics.get('prompt_tokens', 0)}\n"
                                )
                                f.write(
                                    f"Completion tokens: {api_metrics.get('completion_tokens', 0)}\n"
                                )
                                f.write(
                                    f"Total tokens: {api_metrics.get('total_tokens', 0)}\n"
                                )
                                f.write(
                                    f"Estimated cost: ${api_metrics.get('estimated_cost_usd', 0.0):.4f} USD\n\n"
                                )

                                f.write(
                                    "=== Historical API Usage (Last 30 Days) ===\n\n"
                                )
                                f.write(
                                    f"Total runs: {historical_metrics.get('total_runs', 0)}\n"
                                )
                                f.write(
                                    f"Total pages evaluated: {historical_metrics.get('total_pages', 0)}\n"
                                )
                                f.write(
                                    f"Total tokens used: {historical_metrics.get('total_tokens', 0)}\n"
                                )
                                f.write(
                                    f"Total estimated cost: ${historical_metrics.get('total_cost', 0.0):.4f} USD\n\n"
                                )

                            # Now combine the metrics file with the original summary
                            with open(summary_file, "r") as original:
                                original_content = original.read()

                            with open(summary_file, "w") as final:
                                with open(temp_metrics_file, "r") as metrics:
                                    metrics_content = metrics.read()
                                final.write(metrics_content)
                                final.write(original_content)

                            # Remove the temporary file
                            os.remove(temp_metrics_file)

                            logger.success(
                                f"Added API metrics to summary file {summary_file}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to write API metrics to summary file: {e}"
                            )
                except Exception as e:
                    logger.error(f"Error saving API metrics: {e}")

    logger.success("Crawler finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected in main thread")
        sys.exit(0)
