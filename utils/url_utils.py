"""
URL processing and validation utilities
"""

import re
import urllib.robotparser
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, quote

from loguru import logger
from config import Config


def is_valid_url(url, config_obj=None):
    """Check if a URL should be crawled based on patterns and extensions."""
    # Use passed config or default to global Config
    cfg = config_obj or Config

    # Check for invalid schemes
    if not url.startswith(("http://", "https://")):
        return False

    # Parse URL
    parsed = urlparse(url)

    # Check for excluded extensions
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in cfg.EXCLUDED_EXTENSIONS):
        return False

    # Check for excluded patterns
    if any(re.search(pattern, path) for pattern in cfg.EXCLUDED_PATTERNS):
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
            "fbclid",
            "gclid",
        ]:
            if param in query_dict:
                del query_dict[param]

        # Rebuild query string in sorted order for consistency
        if query_dict:
            query_parts = []
            for key in sorted(query_dict.keys()):
                for value in sorted(query_dict[key]):
                    query_parts.append(f"{key}={value}")
            new_query = "&".join(query_parts)
        else:
            new_query = ""

        parsed = parsed._replace(query=new_query)

    # Normalize the path (remove trailing slash)
    path = parsed.path
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
        parsed = parsed._replace(path=path)

    # Ensure the scheme is lowercase
    normalized_url = parsed.geturl()
    if normalized_url.startswith("HTTP"):
        normalized_url = "http" + normalized_url[4:]
    elif normalized_url.startswith("HTTPS"):
        normalized_url = "https" + normalized_url[5:]

    # Handle IDN domains (Unicode to Punycode)
    try:
        parsed = urlparse(normalized_url)
        hostname = parsed.netloc.encode("idna").decode("ascii")
        path = quote(parsed.path, safe="/%")
        normalized = parsed._replace(netloc=hostname, path=path)
        return normalized.geturl()
    except Exception as e:
        logger.warning(f"Error normalizing URL {url}: {e}")
        return normalized_url


def join_url(base, relative):
    """Safely join a base URL and a relative URL."""
    try:
        return urljoin(base, relative)
    except Exception as e:
        logger.error(f"Error joining URLs {base} and {relative}: {e}")
        return None


def get_domain_from_url(url):
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception as e:
        logger.error(f"Error extracting domain from {url}: {e}")
        return ""


def get_path_from_url(url):
    """Extract the path from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.path.lower()
    except Exception as e:
        logger.error(f"Error extracting path from {url}: {e}")
        return ""


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


class RobotsChecker:
    """Class to check and respect robots.txt rules."""

    def __init__(self):
        self.parsers = {}  # Cache for robot parsers by domain
        self.user_agent = Config.USER_AGENT

    def set_user_agent(self, user_agent):
        """Set the user agent string to use for checking permissions."""
        self.user_agent = user_agent

    def _get_parser(self, domain):
        """Get or create a parser for a domain."""
        if domain in self.parsers:
            return self.parsers[domain]

        try:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            parser.set_url(robots_url)
            parser.read()
            self.parsers[domain] = parser
            return parser
        except Exception as e:
            logger.warning(f"Error reading robots.txt for {domain}: {e}")
            # Return a permissive parser on error
            parser = urllib.robotparser.RobotFileParser()
            self.parsers[domain] = parser
            return parser

    def can_fetch(self, url):
        """Check if the URL can be fetched according to robots.txt."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            if not domain:
                return True  # Can't check without a domain

            parser = self._get_parser(domain)
            return parser.can_fetch(self.user_agent, url)
        except Exception as e:
            logger.warning(f"Error checking robots permission for {url}: {e}")
            return True  # Be permissive on error
