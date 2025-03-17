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

    # Updated depth limits
    MAX_DEPTH = 12  # Reduced from 15 to be more focused
    MAX_ADMISSION_DEPTH = 15  # Reduced from 20 to balance thoroughness with performance

    # Worker settings
    NUM_WORKERS = 12  # Increased from 12 to process more URLs concurrently

    # URL limits
    MAX_URLS_PER_DOMAIN = (
        500  # Reduced from 600 to focus on fewer, higher quality pages
    )
    MAX_TOTAL_URLS = 100000  # Set a reasonable maximum

    # Queue management
    MAX_QUEUE_SIZE = 10000  # Maximum queue size
    MAX_URLS_PER_PAGE = 50  # Maximum URLs to extract from a normal page
    MAX_URLS_PER_ADMISSION_PAGE = 100  # Maximum URLs to extract from an admission page

    # Worker settings
    NUM_WORKERS = 12  # Number of concurrent worker tasks

    #
    # Checkpoint Settings
    #

    # Whether to use incremental checkpoints (process in batches during crawling)
    USE_CHECKPOINTS = True

    # Time between checkpoint evaluations in seconds
    CHECKPOINT_INTERVAL = 60

    # Minimum number of application pages to trigger batch evaluation
    MIN_BATCH_SIZE = 10

    # Maximum number of pages to process in one batch
    MAX_BATCH_SIZE = 30

    # Directory to store checkpoint data
    CHECKPOINT_DIR = "checkpoints"  # Relative to OUTPUT_DIR

    # Whether to generate incremental reports at each checkpoint
    CHECKPOINT_REPORTS = True

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
        r"/blog/",
        r"/blogs/",
        r"/article/",
        r"/articles/",
        r"/press/",
        r"/pressrelease/",
        r"/press-release/",
        r"/media/",
        r"/story/",
        r"/stories/",
        r"/history/",
        r"/testimonials/",
        r"/gallery/",
        r"/photo/",
        r"/photos/",
        r"/video/",
        r"/videos/",
        r"/podcast/",
        r"/webinar/",
        r"/award/",
        r"/awards/",
        r"/rankings/",
        r"/events/",
        r"/schedule/",
        r"/calendar/",
        r"/academic-calendar/",
        r"/comment/",
        r"/comments/",
        r"/user/",
        r"/users/",
        r"/profile/",
        r"/profiles/",
        r"/staff/",
        r"/faculty/",
        r"/department/",
        r"/departments/",
        r"/housing/",
        r"/library/",
        r"/libraries/",
        r"/dining/",
        r"/food/",
        r"/cafe/",
        r"/restaurant/",
        r"/parking/",
        r"/map/",
        r"/maps/",
        r"/directions/",
        r"/transportation/",
        r"/bus/",
        r"/shuttle/",
        r"/print/",
        r"/share/",
        r"/email/",
        r"/feedback/",
        r"/help/",
        r"/faq/",
        r"/support/",
        r"/ticket/",
        r"/tickets/",
        r"/page/\d+/",
        r"/p/\d+/",
        r"/\d{4}/\d{2}/\d{2}/",
        r"/\d{4}/\d{2}/",
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
        # Additional file extensions
        ".ico",
        ".tif",
        ".tiff",
        ".bmp",
        ".webp",
        ".webm",
        ".ogg",
        ".ogv",
        ".oga",
        ".flv",
        ".swf",
        ".xml",
        ".json",
        ".csv",
        ".tsv",
        ".txt",
        ".rtf",
        ".md",
        ".markdown",
        ".asp",
        ".aspx",
        ".exe",
        ".bin",
        ".iso",
        ".dmg",
        ".jar",
        ".war",
        ".ear",
        ".class",
        ".dll",
        ".so",
        ".apk",
        ".ipa",
        ".epub",
        ".mobi",
        ".azw",
        ".azw3",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
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

    # Add How-to-Apply report generation
    GENERATE_HOW_TO_APPLY = True  # Whether to generate focused "How to Apply" report

    # Domain-based rate limiting
    DOMAIN_RATE_LIMITS = {
        "default": 1.0,  # Default delay between requests to same domain
        "max_rate_limit": 5.0,  # Maximum rate limit for any domain
    }

    # Adaptive discovery based on depth
    DISCOVERY_LIMITS = {
        "shallow": 50,  # URLs to extract from depth 0-3
        "medium": 30,  # URLs to extract from depth 4-6
        "deep": 15,  # URLs to extract from depth 7+
        "admission_domain": 100,  # URLs to extract from admission domains
    }

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

        # Validate checkpoint settings
        if cls.USE_CHECKPOINTS:
            if cls.MIN_BATCH_SIZE <= 0:
                print("ERROR: MIN_BATCH_SIZE must be greater than 0")
                return False
            if cls.MAX_BATCH_SIZE < cls.MIN_BATCH_SIZE:
                print(
                    "ERROR: MAX_BATCH_SIZE must be greater than or equal to MIN_BATCH_SIZE"
                )
                return False
            if cls.CHECKPOINT_INTERVAL <= 0:
                print("ERROR: CHECKPOINT_INTERVAL must be greater than 0")
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
            "use_checkpoints": cls.USE_CHECKPOINTS,
            "checkpoint_interval": cls.CHECKPOINT_INTERVAL,
            "batch_size": f"{cls.MIN_BATCH_SIZE}-{cls.MAX_BATCH_SIZE}",
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

        # Add checkpoint settings to summary
        if cls.USE_CHECKPOINTS:
            print(f"Checkpoint interval: {summary['checkpoint_interval']}s")
            print(f"Batch size: {summary['batch_size']}")
        else:
            print("Checkpoints: Disabled")

        print("============================\n")

    @classmethod
    def update_from_args(cls, args):
        """Update configuration from command line arguments."""
        # Update basic settings
        if hasattr(args, "depth"):
            cls.MAX_DEPTH = args.depth
        if hasattr(args, "workers"):
            cls.NUM_WORKERS = args.workers
        if hasattr(args, "max_urls"):
            cls.MAX_TOTAL_URLS = args.max_urls
        if hasattr(args, "model"):
            cls.MODEL_NAME = args.model
        if hasattr(args, "use_db"):
            cls.USE_SQLITE = args.use_db
        if hasattr(args, "html_report"):
            cls.SAVE_HTML_REPORT = args.html_report
        if hasattr(args, "csv"):
            cls.SAVE_CSV = args.csv

        # Update checkpoint settings
        if hasattr(args, "disable_checkpoints"):
            cls.USE_CHECKPOINTS = not args.disable_checkpoints
        if hasattr(args, "checkpoint_interval"):
            cls.CHECKPOINT_INTERVAL = args.checkpoint_interval
        if hasattr(args, "min_batch_size"):
            cls.MIN_BATCH_SIZE = args.min_batch_size
        if hasattr(args, "max_batch_size"):
            cls.MAX_BATCH_SIZE = args.max_batch_size

        # Output directory
        if hasattr(args, "output_dir"):
            cls.OUTPUT_DIR = args.output_dir
            cls.REPORT_DIR = os.path.join(args.output_dir, "reports")

        # Update logging settings
        if hasattr(args, "log_level"):
            cls.LOG_LEVEL = args.log_level
        if hasattr(args, "log_file"):
            cls.LOG_FILE = args.log_file
