"""
Configuration settings for the University Application Crawler
"""

import os
import sys
from typing import Dict, List, Set, Any, Optional

from universities import SEED_UNIVERSITIES as universities


class Config:
    """Central configuration for the crawler."""

    #
    # University Targets
    #

    # List of seed universities to crawl
    SEED_UNIVERSITIES = universities

    # Known admission subdomains to add as seeds
    ADMISSION_SUBDOMAINS = {
        # "mit.edu": ["admissions.mit.edu", "apply.mit.edu"],
        # "stanford.edu": [
        #     "admission.stanford.edu",
        #     "apply.stanford.edu",
        #     "admissions.stanford.edu",
        #     "undergrad.stanford.edu",
        # ],
        # "harvard.edu": ["admissions.harvard.edu", "college.harvard.edu/admissions"],
        # "princeton.edu": ["admission.princeton.edu"],
        # "yale.edu": ["admissions.yale.edu", "apply.yale.edu"],
    }

    #
    # Crawling Settings
    #

    # Depth limits
    MAX_DEPTH = 12  # Regular crawl depth
    MAX_ADMISSION_DEPTH = 15  # Deeper crawl for admission-related domains

    # Request settings
    REQUEST_TIMEOUT = 15  # Seconds
    REQUEST_DELAY = 1  # Seconds between requests
    RESPECT_ROBOTS_TXT = True  # Whether to respect robots.txt

    # URL limits
    MAX_URLS_PER_DOMAIN = 600  # Maximum URLs to crawl per domain
    MAX_TOTAL_URLS = 2000000  # Maximum total URLs to crawl

    # Worker settings
    NUM_WORKERS = 12  # Number of concurrent worker tasks

    #
    # Application Keywords and Indicators
    #

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

    #
    # URL Patterns
    #

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
        r"/privacy-policy/",
        r"/terms/",
        r"/campus-map/",
        r"/campus-tour/",
        r"/privacy",
        r"/terms",
        r"/careers",
        r"/jobs",
        r"/employment",
        r"/opportunities",
        r"/opportunity",
        r"/visit",
        r"/tour",
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

    #
    # OpenAI Configuration
    #

    # Model settings
    MODEL_NAME = "gpt-4o-mini"  # Model to use for evaluation

    # API settings
    MAX_EVAL_BATCH = 10  # Evaluate this many URLs in one batch
    MAX_CONCURRENT_API_CALLS = 5  # Maximum concurrent API calls

    # OpenAI API key - load from environment
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        print("WARNING: OPENAI_API_KEY environment variable not set")

    # Cost tracking
    PROMPT_TOKEN_COST = 0.00015  # Cost per 1K tokens for prompt
    COMPLETION_TOKEN_COST = 0.0006  # Cost per 1K tokens for completion
    CACHED_TOKEN_COST = 0.000075  # Cost per 1K tokens for cached prompt

    #
    # Database Settings
    #

    # SQLite settings
    USE_SQLITE = True  # Whether to use SQLite database
    DB_PATH = os.path.join(
        os.path.dirname(__file__), "crawler_data.db"
    )  # Database path

    #
    # User Agent Settings
    #

    # Primary user agent
    USER_AGENT = "University-Application-Crawler/1.0 (contact: ghoulbites777@gmail.com)"

    # User agent rotation settings
    USER_AGENT_ROTATION = True  # Whether to rotate user agents
    USER_AGENTS = [
        "University-Application-Crawler/1.0 (contact: ghoulbites777@gmail.com)",
        "UniversityApplicationFinder/1.0 (contact: ghoulbites777@gmail.com)",
        "EducationalCrawler/1.0 (contact: ghoulbites777@gmail.com)",
    ]

    #
    # Output Settings
    #

    # Output paths
    OUTPUT_DIR = "outputs"  # Directory for saving results
    REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")  # Directory for reports

    # Output formats
    SAVE_HTML_REPORT = False  # Whether to generate HTML report
    SAVE_CSV = False  # Whether to export to CSV

    #
    # Logging Settings
    #

    # Log levels
    LOG_LEVEL = "INFO"

    # Log files
    LOG_FILE = "crawler.log"
    ERROR_LOG_FILE = "errors.log"

    @classmethod
    def validate(cls) -> bool:
        """Validate the configuration."""
        # Check for required settings
        if not cls.SEED_UNIVERSITIES:
            print("ERROR: No seed universities defined")
            return False

        # Validate API key if evaluation is enabled
        if not cls.OPENAI_API_KEY and not getattr(cls, "SKIP_EVALUATION", False):
            print("ERROR: OpenAI API key is required for evaluation")
            print(
                "Set the OPENAI_API_KEY environment variable or enable SKIP_EVALUATION"
            )
            return False

        return True

    @classmethod
    def summarize(cls) -> Dict[str, Any]:
        """Return a summary of the configuration."""
        return {
            "universities": [u["name"] for u in cls.SEED_UNIVERSITIES],
            "max_depth": cls.MAX_DEPTH,
            "max_urls": cls.MAX_TOTAL_URLS,
            "num_workers": cls.NUM_WORKERS,
            "model": cls.MODEL_NAME,
            "use_database": cls.USE_SQLITE,
        }

    @classmethod
    def print_summary(cls) -> None:
        """Print a summary of the configuration."""
        summary = cls.summarize()
        print("\n=== Configuration Summary ===")
        print(f"Universities: {', '.join(summary['universities'])}")
        print(f"Max depth: {summary['max_depth']}")
        print(f"Max URLs: {summary['max_urls']}")
        print(f"Workers: {summary['num_workers']}")
        print(f"Model: {summary['model']}")
        print(f"Using database: {summary['use_database']}")
        print("============================\n")
