"""
Unified URL processing service to eliminate duplicate functionality
"""

import asyncio
import re
import socket
import urllib.robotparser
from urllib.parse import urlparse, parse_qs, quote

from loguru import logger
from config import Config


# Global set of failed domains and failure counts
failed_domains = set()
domain_failure_counts = {}
MAX_DOMAIN_FAILURES = 3  # Maximum failures before blacklisting a domain


# Add this function to verify domain existence
async def is_valid_domain(domain):
    """Check if a domain is valid by performing a DNS lookup."""
    # Skip check if domain is already known to be invalid
    if domain in failed_domains:
        return False

    # Use a thread for the blocking DNS lookup
    loop = asyncio.get_running_loop()
    try:
        # Try to resolve the domain
        await loop.run_in_executor(None, socket.gethostbyname, domain)
        return True
    except socket.gaierror:
        # Track failure count for this domain
        domain_failure_counts[domain] = domain_failure_counts.get(domain, 0) + 1

        # If we've failed too many times, add to the blacklist
        if domain_failure_counts[domain] >= MAX_DOMAIN_FAILURES:
            logger.warning(
                f"Blacklisting domain after {MAX_DOMAIN_FAILURES} failures: {domain}"
            )
            failed_domains.add(domain)
        return False


def normalize_url(url):
    """
    Enhanced URL normalization that prevents loops and cleans malformed URLs
    """
    if not url:
        return url

    try:
        # Clean common problematic characters from URLs
        # This handles cases where HTML or quotes get into URLs
        for char in ["<", ">", '"', "'", "\\", "\n", "\r", "\t"]:
            url = url.replace(char, "")

        # Replace URL-encoded versions of these characters too
        url = url.replace("%22", "")  # Encoded quote
        url = url.replace("%3C", "")  # Encoded <
        url = url.replace("%3E", "")  # Encoded >

        # Parse URL
        parsed = urlparse(url)

        # Normalize scheme to lowercase
        scheme = parsed.scheme.lower()
        if not scheme:
            scheme = "http"

        # Remove fragment
        parsed = parsed._replace(fragment="", scheme=scheme)

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
                "ref",
                "source",
                "mc_cid",
                "mc_eid",
                "_ga",
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

        # Process and normalize the path
        path = parsed.path

        # Ensure path starts with / if it exists
        if path and not path.startswith("/"):
            path = "/" + path

        # Remove trailing slash for non-root paths
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]

        # Fix repeating path segments - this addresses loop issues
        path_parts = [p for p in path.split("/") if p]
        clean_parts = []

        for part in path_parts:
            # Don't add if it would create a repeat
            if not clean_parts or part != clean_parts[-1]:
                clean_parts.append(part)

        # Check for suspicious path length (likely a crawler trap)
        if len(clean_parts) > 10:
            # Only keep important URL paths in deep URLs
            if not any(
                important in "/".join(clean_parts)
                for important in ["apply", "admission", "undergraduate"]
            ):
                # Truncate non-important deep paths
                clean_parts = clean_parts[:5]
                logger.debug(f"Truncating suspiciously deep path: {path}")

        # Reconstruct the path
        clean_path = "/" + "/".join(clean_parts)
        if not clean_path or clean_path == "/":
            clean_path = "/"

        # URL-encode the path (preserving slashes)
        clean_path = quote(clean_path, safe="/%")
        parsed = parsed._replace(path=clean_path)

        # Handle IDN domains (Unicode to Punycode)
        hostname = parsed.netloc.encode("idna").decode("ascii")
        parsed = parsed._replace(netloc=hostname)

        # Final URL
        final_url = parsed.geturl()

        # One last safety check for max length
        if len(final_url) > 2000:  # Common URL length limit
            logger.warning(
                f"URL exceeds maximum length, truncating: {final_url[:50]}..."
            )
            return final_url[:2000]

        return final_url
    except Exception as e:
        logger.warning(f"Error normalizing URL {url}: {e}")
        # Try to return something useful if possible
        sanitized = re.sub(r'[<>"\'\\]', "", url)
        return sanitized[:2000] if len(sanitized) > 2000 else sanitized


def is_valid_url(url):
    """Check if a URL should be crawled based on patterns and extensions."""
    # Use passed config or default to global Config
    if not url:
        return False

    # Check for invalid schemes
    if not url.startswith(("http://", "https://")):
        return False

    # Parse URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    full_url = url.lower()  # For matching patterns in the full URL (domain + path)

    # Check for excluded extensions
    if any(path.endswith(ext) for ext in Config.EXCLUDED_EXTENSIONS):
        return False

    # Check for excluded patterns in the path
    if any(re.search(pattern, path) for pattern in Config.EXCLUDED_PATTERNS):
        return False

    # Check for excluded patterns in the full URL if such a list exists in config
    if hasattr(Config, "EXCLUDED_FULL_URL_PATTERNS"):
        if any(
            re.search(pattern, full_url)
            for pattern in Config.EXCLUDED_FULL_URL_PATTERNS
        ):
            return False

    # Check for excessive query parameters (often search results or session tracking)
    if parsed.query and len(parsed.query) > 100:
        return False

    # Check for suspicious patterns using the module-level constant
    if any(re.search(pattern, path) for pattern in Config.SUSPICIOUS_PATTERNS):
        return False

    # Check for long paths with repeating segments (crawler traps)
    path_segments = [p for p in path.split("/") if p]
    if len(path_segments) > 8:
        # Allow deep paths only if they contain important keywords
        if not any(
            keyword in path
            for keyword in ["apply", "admission", "freshman", "application"]
        ):
            return False

    # Check for duplicate path segments (potential crawler trap)
    segment_counts = {}
    for segment in path_segments:
        segment_counts[segment] = segment_counts.get(segment, 0) + 1
        if segment_counts[segment] > 2:  # Allow at most 2 occurrences
            return False

    return True


def get_url_priority(url, university):
    """Determine priority for a URL (lower is higher priority)."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # Extract path depth for use in prioritization
    path_depth = len([p for p in path.split("/") if p])

    # Base priority starts at 10 plus depth penalty
    base_priority = 10 + path_depth

    # Highest priority: Look for exact application paths (priority 0-1)
    if any(pattern in path for pattern in Config.HIGH_PRIORITY_PATTERNS):
        return 0

    # Very high priority: Application forms and portals (priority 1-2)
    application_indicators = Config.VERY_HIGH_PRIORITY_PATTERNS

    for i, pattern in enumerate(application_indicators):
        if re.search(pattern, path):
            return 1 + (i * 0.1)  # Between 1 and 2

    # Second highest: Admission subdomains with application paths (priority 2-3)
    if ("admission" in domain or "apply" in domain or "undergrad" in domain) and any(
        p in path
        for p in ["/apply", "/admission", "/application", "/portal", "/first-year"]
    ):
        return 2

    # Third highest: General admission subdomains (priority 3-4)
    if any(x in domain for x in ["admission", "apply", "undergrad", "freshman"]):
        return 3

    # Fourth highest: Important paths on any domain (priority 4-6)
    for i, pattern in enumerate(Config.HIGH_PRIORITY_PATTERNS):
        if pattern in path:
            return 4 + (i * 0.1)  # Small increments to maintain ordering of patterns

    # Fifth highest: URLs with application keywords in path (priority 6-8)
    for i, keyword in enumerate(Config.APPLICATION_KEYWORDS):
        if keyword in path:
            return 6 + (i * 0.1)

    # Default priority - consider depth from homepage
    # Exponential penalty for depth to strongly prefer shallow URLs
    return base_priority + (path_depth**1.5)


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
