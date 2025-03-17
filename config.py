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
    # Crawling Settings
    #

    # Updated depth limits
    MAX_DEPTH = 6  # Reduced from 15 to be more focused
    MAX_ADMISSION_DEPTH = 12  # Reduced from 20 to balance thoroughness with performance

    # Worker settings
    NUM_WORKERS = 18  # Increased from 12 to process more URLs concurrently

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
    # University Targets
    #

    # List of seed universities to crawl
    SEED_UNIVERSITIES = universities

    # Known admission subdomains to add as seeds
    ADMISSION_SUBDOMAINS = {
        "mit.edu": [
            "admissions.mit.edu",
            "apply.mit.edu",
        ],
        "cam.ac.uk": [
            "admissions.cam.ac.uk",
            "apply.cam.ac.uk",
            "undergraduate.study.cam.ac.uk",
        ],
        "ox.ac.uk": [
            "admissions.ox.ac.uk",
            "apply.ox.ac.uk",
        ],
        "harvard.edu": [
            "admissions.harvard.edu",
            "college.harvard.edu/admissions",
        ],
        "stanford.edu": [
            "admission.stanford.edu",
            "apply.stanford.edu",
            "admissions.stanford.edu",
            "undergrad.stanford.edu",
        ],
        "imperial.ac.uk": [
            "admissions.imperial.ac.uk",
            "apply.imperial.ac.uk",
        ],
        "ethz.ch": [
            "admissions.ethz.ch",
            "apply.ethz.ch",
        ],
        "nus.edu.sg": [
            "admissions.nus.edu.sg",
            "apply.nus.edu.sg",
        ],
        "ucl.ac.uk": [
            "admissions.ucl.ac.uk",
            "apply.ucl.ac.uk",
        ],
        "berkeley.edu": [
            "admissions.berkeley.edu",
            "apply.berkeley.edu",
        ],
        "uchicago.edu": [
            "admissions.uchicago.edu",
            "apply.uchicago.edu",
        ],
        "upenn.edu": [
            "admissions.upenn.edu",
            "apply.upenn.edu",
        ],
        "cornell.edu": [
            "admissions.cornell.edu",
            "apply.cornell.edu",
        ],
        "unimelb.edu.au": [
            "admissions.unimelb.edu.au",
            "apply.unimelb.edu.au",
        ],
        "caltech.edu": [
            "admissions.caltech.edu",
            "apply.caltech.edu",
        ],
        "yale.edu": [
            "admissions.yale.edu",
            "apply.yale.edu",
        ],
        "pku.edu.cn": [
            "admissions.pku.edu.cn",
            "apply.pku.edu.cn",
        ],
        "princeton.edu": [
            "admission.princeton.edu",
            "apply.princeton.edu",
        ],
        "unsw.edu.au": [
            "admissions.unsw.edu.au",
            "apply.unsw.edu.au",
        ],
        "sydney.edu.au": [
            "admissions.sydney.edu.au",
            "apply.sydney.edu.au",
        ],
        "utoronto.ca": [
            "admissions.utoronto.ca",
            "apply.utoronto.ca",
        ],
        "ed.ac.uk": [
            "admissions.ed.ac.uk",
            "apply.ed.ac.uk",
        ],
        "columbia.edu": [
            "undergraduate.admissions.columbia.edu",
            "apply.college.columbia.edu",
        ],
        "univ-psl.fr": [
            "admissions.univ-psl.fr",
            "apply.univ-psl.fr",
        ],
        "tsinghua.edu.cn": [
            "admissions.tsinghua.edu.cn",
            "apply.tsinghua.edu.cn",
        ],
        "ntu.edu.sg": [
            "admissions.ntu.edu.sg",
            "apply.ntu.edu.sg",
        ],
        "hku.hk": [
            "admissions.hku.hk",
            "apply.hku.hk",
        ],
        "jhu.edu": [
            "admissions.jhu.edu",
            "apply.jhu.edu",
        ],
        "u-tokyo.ac.jp": [
            "admissions.u-tokyo.ac.jp",
            "apply.u-tokyo.ac.jp",
        ],
        "ucla.edu": [
            "admissions.ucla.edu",
            "apply.ucla.edu",
        ],
        "mcgill.ca": [
            "admissions.mcgill.ca",
            "apply.mcgill.ca",
        ],
        "manchester.ac.uk": [
            "admissions.manchester.ac.uk",
            "apply.manchester.ac.uk",
        ],
        "umich.edu": [
            "admissions.umich.edu",
            "apply.umich.edu",
        ],
        "anu.edu.au": [
            "admissions.anu.edu.au",
            "apply.anu.edu.au",
        ],
        "ubc.ca": [
            "admissions.ubc.ca",
            "apply.ubc.ca",
        ],
        "epfl.ch": [
            "admissions.epfl.ch",
            "apply.epfl.ch",
        ],
        "tum.de": [
            "admissions.tum.de",
            "apply.tum.de",
        ],
        "polytechnique.edu": [
            "admissions.polytechnique.edu",
            "apply.polytechnique.edu",
        ],
        "nyu.edu": [
            "admissions.nyu.edu",
            "apply.nyu.edu",
        ],
        "kcl.ac.uk": [
            "admissions.kcl.ac.uk",
            "apply.kcl.ac.uk",
        ],
        "snu.ac.kr": [
            "admissions.snu.ac.kr",
            "apply.snu.ac.kr",
        ],
        "monash.edu": [
            "admissions.monash.edu",
            "apply.monash.edu",
        ],
        "uq.edu.au": [
            "admissions.uq.edu.au",
            "apply.uq.edu.au",
        ],
        "zju.edu.cn": [
            "admissions.zju.edu.cn",
            "apply.zju.edu.cn",
        ],
        "lse.ac.uk": [
            "admissions.lse.ac.uk",
            "apply.lse.ac.uk",
        ],
        "kyoto-u.ac.jp": [
            "admissions.kyoto-u.ac.jp",
            "apply.kyoto-u.ac.jp",
        ],
        "tudelft.nl": [
            "admissions.tudelft.nl",
            "apply.tudelft.nl",
        ],
        "northwestern.edu": [
            "admissions.northwestern.edu",
            "apply.northwestern.edu",
        ],
        "cuhk.edu.hk": [
            "admissions.cuhk.edu.hk",
            "apply.cuhk.edu.hk",
        ],
        "fudan.edu.cn": [
            "admissions.fudan.edu.cn",
            "apply.fudan.edu.cn",
        ],
        "sjtu.edu.cn": [
            "admissions.sjtu.edu.cn",
            "apply.sjtu.edu.cn",
        ],
        "cmu.edu": [
            "admissions.cmu.edu",
            "apply.cmu.edu",
        ],
        "uva.nl": [
            "admissions.uva.nl",
            "apply.uva.nl",
        ],
        "uni-muenchen.de": [
            "admissions.uni-muenchen.de",
            "apply.uni-muenchen.de",
        ],
        "bristol.ac.uk": [
            "admissions.bristol.ac.uk",
            "apply.bristol.ac.uk",
        ],
        "kaist.ac.kr": [
            "admissions.kaist.ac.kr",
            "apply.kaist.ac.kr",
        ],
        "duke.edu": [
            "admissions.duke.edu",
            "apply.duke.edu",
        ],
        "utexas.edu": [
            "admissions.utexas.edu",
            "apply.utexas.edu",
        ],
        "sorbonne-universite.fr": [
            "admissions.sorbonne-universite.fr",
            "apply.sorbonne-universite.fr",
        ],
        "ust.hk": [
            "admissions.ust.hk",
            "apply.ust.hk",
        ],
        "kuleuven.be": [
            "admissions.kuleuven.be",
            "apply.kuleuven.be",
        ],
        "ucsd.edu": [
            "admissions.ucsd.edu",
            "apply.ucsd.edu",
        ],
        "washington.edu": [
            "admissions.washington.edu",
            "apply.washington.edu",
        ],
        "illinois.edu": [
            "admissions.illinois.edu",
            "apply.illinois.edu",
        ],
        "polyu.edu.hk": [
            "admissions.polyu.edu.hk",
            "apply.polyu.edu.hk",
        ],
        "um.edu.my": [
            "admissions.um.edu.my",
            "apply.um.edu.my",
        ],
        "warwick.ac.uk": [
            "admissions.warwick.ac.uk",
            "apply.warwick.ac.uk",
        ],
        "auckland.ac.nz": [
            "admissions.auckland.ac.nz",
            "apply.auckland.ac.nz",
        ],
        "ntu.edu.tw": [
            "admissions.ntu.edu.tw",
            "apply.ntu.edu.tw",
        ],
        "cityu.edu.hk": [
            "admissions.cityu.edu.hk",
            "apply.cityu.edu.hk",
        ],
        "universite-paris-saclay.fr": [
            "admissions.universite-paris-saclay.fr",
            "apply.universite-paris-saclay.fr",
        ],
        "uwa.edu.au": [
            "admissions.uwa.edu.au",
            "apply.uwa.edu.au",
        ],
        "brown.edu": [
            "admissions.brown.edu",
            "apply.brown.edu",
        ],
        "kth.se": [
            "admissions.kth.se",
            "apply.kth.se",
        ],
        "leeds.ac.uk": [
            "admissions.leeds.ac.uk",
            "apply.leeds.ac.uk",
        ],
        "gla.ac.uk": [
            "admissions.gla.ac.uk",
            "apply.gla.ac.uk",
        ],
        "yonsei.ac.kr": [
            "admissions.yonsei.ac.kr",
            "apply.yonsei.ac.kr",
        ],
        "dur.ac.uk": [
            "admissions.dur.ac.uk",
            "apply.dur.ac.uk",
        ],
        "korea.ac.kr": [
            "admissions.korea.ac.kr",
            "apply.korea.ac.kr",
        ],
        "osaka-u.ac.jp": [
            "admissions.osaka-u.ac.jp",
            "apply.osaka-u.ac.jp",
        ],
        "tcd.ie": [
            "admissions.tcd.ie",
            "apply.tcd.ie",
        ],
        "southampton.ac.uk": [
            "admissions.southampton.ac.uk",
            "apply.southampton.ac.uk",
        ],
        "psu.edu": [
            "admissions.psu.edu",
            "apply.psu.edu",
        ],
        "birmingham.ac.uk": [
            "admissions.birmingham.ac.uk",
            "apply.birmingham.ac.uk",
        ],
        "lu.se": [
            "admissions.lu.se",
            "apply.lu.se",
        ],
        "usp.br": [
            "admissions.usp.br",
            "apply.usp.br",
        ],
        "msu.ru": [
            "admissions.msu.ru",
            "apply.msu.ru",
        ],
        "uni-heidelberg.de": [
            "admissions.uni-heidelberg.de",
            "apply.uni-heidelberg.de",
        ],
        "adelaide.edu.au": [
            "admissions.adelaide.edu.au",
            "apply.adelaide.edu.au",
        ],
        "uts.edu.au": [
            "admissions.uts.edu.au",
            "apply.uts.edu.au",
        ],
        "titech.ac.jp": [
            "admissions.titech.ac.jp",
            "apply.titech.ac.jp",
        ],
        "uzh.ch": [
            "admissions.uzh.ch",
            "apply.uzh.ch",
        ],
        "bu.edu": [
            "admissions.bu.edu",
            "apply.bu.edu",
        ],
        "unam.mx": [
            "admissions.unam.mx",
            "apply.unam.mx",
        ],
        "uba.ar": [
            "admissions.uba.ar",
            "apply.uba.ar",
        ],
        "gatech.edu": [
            "admissions.gatech.edu",
            "apply.gatech.edu",
        ],
        "st-andrews.ac.uk": [
            "admissions.st-andrews.ac.uk",
            "apply.st-andrews.ac.uk",
        ],
        "fu-berlin.de": [
            "admissions.fu-berlin.de",
            "apply.fu-berlin.de",
        ],
        "purdue.edu": [
            "admissions.purdue.edu",
            "apply.purdue.edu",
        ],
        "postech.ac.kr": [
            "admissions.postech.ac.kr",
            "apply.postech.ac.kr",
        ],
    }

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

    PRIORITY_PATTERNS = [
        "/apply",
        "/admission",
        "/admissions",
        "/undergraduate",
        "/freshman",
        "/first-year",
        "/transfer",
        "/application",
        "/applications",
        "/apply-now",
        "/prospective",
        "/portal",
        "/submit",
        "/applicant",
        "/start",
        "/begin",
        "/create",
        "/status",
        "/common-app",
        "/common-application",
        "/coalition-app",
        "/programs",
        "/program",
        "/degree",
        "/degrees",
        "/courses",
        "/course",
        "/majors",
        "/major",
        "/academics",
        "/academic",
        "/study",
        "/enroll",
        "/enrollment",
        "/register",
        "/registration",
        "/international",
        "/online",
        # "/graduate",    # Not undergraduate focused
        # "/grad",        # Not undergraduate focused
        # "/student",     # Too general
        # "/students",    # Too general
        # "/campus",      # Not directly application-related
        # "/housing",     # Not relevant to application process
        # "/financial-aid",  # Secondary information
        # "/scholarships",   # Secondary information
        # "/tuition",        # Secondary information
        # "/fees",           # Secondary information
        # "/cost",           # Secondary information
        # "/calendar",       # Not directly application-related
        # "/events",         # Not relevant to applications
        # "/visit",          # Not core to application process
        # "/tour",           # Not core to application process
        # "/contact",        # Too general
        # "/about",          # Too general
        # "/faq",            # Too general
        # "/services",       # Not directly application-related
        # "/support",        # Not directly application-related
        # "/help",           # Too general
        # "/resources",      # Too general
        # "/life",           # Not relevant to applications
        # "/community",      # Not relevant to applications
        # "/clubs",          # Not relevant to applications
        # "/organizations",  # Not relevant to applications
        # "/societies",      # Not relevant to applications
        # "/research",       # Not undergraduate-focused
        # "/faculty",        # Not directly application-related
        # "/staff",          # Not directly application-related
        # "/directory",      # Not directly application-related
        # "/news",           # Not application-related
        # "/press",          # Not application-related
        # "/media",          # Not application-related
        # "/blog",           # Not application-related
        # "/stories",        # Not application-related
        # "/gallery",        # Not application-related
        # "/photos",         # Not application-related
        # "/video",          # Not application-related
        # "/videos",         # Not application-related
        # "/podcast",        # Not application-related
        # "/webinar",        # Not application-related
        # "/award",          # Not application-related
        # "/awards",         # Not application-related
        # "/rankings",       # Not directly application-related
        # "/testimonials",   # Not directly application-related
        # "/history",        # Not application-related
        # "/mission",        # Not application-related
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

    # Very high-priority URL patterns - most specific patterns first
    VERY_HIGH_PRIORITY_PATTERNS = [
        "/apply$",
        "/apply/$",
        "/application$",
        "/application/$",
        "/portal",
        "/admission$",
        "/admission/$",
        "/admissions$",
        "/admissions/$",
        "/apply-now",
        "/apply-now/",
        "/apply-now$",
        "/apply-now/$",
        "/prospective$",
        "/prospective/$",
        "/prospective-students$",
        "/prospective-students/$",
        "/prospective-students",
        "/prospective-students/",
        "/prospective-student$",
        "/prospective-student/$",
        "/prospective-student",
        "/prospective-student/",
        "/enroll$",
        "/enroll/$",
        "/enroll-now$",
        "/enroll-now/$",
        "/enroll-now",
        "/enroll-now/",
        "/enrollment$",
        "/enrollment/$",
        "/enrollment-now$",
        "/enrollment-now/$",
        "/enrollment-now",
        "/enrollment-now/",
        "/register$",
        "/register/$",
        "/register-now$",
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
        # Additional graduate-specific pages (avoiding non-undergrad content)
        r"/grad-admissions/",
        r"/graduate-admissions/",
        r"/graduate-programs/",
        r"/masters/",
        r"/phd/",
        r"/doctoral/",
        r"/postgraduate/",
        # Student life, study abroad, orientation, and campus services
        r"/campus-life/",
        r"/student-life/",
        r"/student-services/",
        r"/career-services/",
        r"/study-abroad/",
        r"/orientation/",
        # Administrative, IT, and support sections (typically non-academic)
        r"/virtual-tour/",
        r"/sitemap",
        r"/intranet/",
        r"/it-support/",
        r"/helpdesk/",
        # Non-credit, continuing, and executive education sections
        r"/noncredit/",
        r"/professional-development/",
        r"/continuing-education/",
        r"/executive-education/",
        r"/non-degree/",
        # Retail, donation, and merchandise pages
        r"/bookstore/",
        r"/shop/",
        r"/store/",
        r"/merchandise/",
        # Financial, legal, and policy pages (usually support or administrative)
        r"/financial-aid/",
        r"/scholarships/",
        r"/tuition/",
        r"/fees/",
        r"/disclaimer/",
        r"/cookie/",
        r"/policies?/",  # matches /policy/ and /policies/
        r"/policy/",
        # Alumni, donor, and advancement-related pages
        r"/alumni-news/",
        r"/commencement/",
        r"/reunion/",
        r"/advancement/",
        r"/donors?/",  # covers singular and plural forms
        r"/foundation/",
        # Media, public relations, and communications sections
        r"/newsletter/",
        r"/newsroom/",
        r"/press-kit/",
        # Governance, administration, and institutional pages
        r"/board-of-trustees/",
        r"/institutional-research/",
        r"/administration/",
        r"/executive/",
        # Research centers and innovation hubs (usually separate from course listings)
        r"/research-center/",
        r"/centers?/",  # matches /center/ and /centers/
        r"/center/",
        r"/innovation/",
        r"/incubator/",
        # Miscellaneous non-academic pages
        r"/safety/",
        r"/security/",
        r"/emergency/",
        r"/volunteer/",
        r"/clubs/",
        r"/organizations/",
        r"/societies/",
        r"/ministry/",
        r"/chapel/",
        r"/religion/",
        r"/advertise/",
        r"/partners/",
        # Event-related pages not previously covered
        r"/seminar/",
        r"/conference/",
        r"/symposium/",
        r"/talks?/",  # covers both /talk/ and /talks/
        r"/workshop/",
        r"/virtual-event/",
        # Advising and academic support (often separate from course listings/applications)
        r"/advising/",
        r"/academic-advising/",
        r"/student-advising/",
        # Social media and external platform pages
        r"/facebook/",
        r"/twitter/",
        r"/instagram/",
        r"/linkedin/",
        r"/youtube/",
        r"/vimeo/",
        # Community and discussion pages
        r"/forum/",
        r"/community/",
        r"/discussion/",
        # Sustainability and environmental initiatives (typically administrative or outreach)
        r"/sustainability/",
        r"/green-initiatives/",
        r"/environment/",
        r"/recycling/",
        r"/sustainability-reports/",
        # Accreditation and quality assurance pages
        r"/accreditation/",
        r"/accredited/",
        # Governance, planning, and institutional leadership pages
        r"/strategic-planning/",
        r"/governance/",
        r"/board/",
        # Funding, research grants, and financial awards
        r"/funding/",
        r"/grants?/",  # covers both /grant/ and /grants/
        # Emergency, campus safety, and related services
        r"/police/",
        r"/alerts/",
        # Surveys and feedback pages (beyond basic help/FAQ)
        r"/survey/",
        # International-specific content if managed separately
        r"/international-admissions/",
        r"/international-programs/",
        # Additional media and broadcast sections
        r"/press-conference/",
        r"/press-briefing/",
        r"/webcast/",
        # Exclude pages that display deadlines or FAQs (often not application forms)
        r"/deadlines",
        r"/faqs?(/|$)",
        # Exclude internal applicant portals and transfer requirements pages
        r"/applicantportal/",
        r"/transfer-requirements/",
        # Exclude pages that are likely media attribution or non‐content (e.g. picture credits)
        r"/picture[-_]?credits",
        # Exclude certain internal admin or network pages not relevant to applications
        r"/networks",
        r"/culture-change",
        # Exclude URLs that include cookie/disclaimer markers (often inserted by the CMS)
        r"/(@@|%40%40)[\w\-]+",  # catches patterns like @@disable-cookies, %40%40enable-cookies, etc.
    ]

    EXCLUDED_FULL_URL_PATTERNS = [
        # Microsoft Office Online
        r"https?://.*\.sharepoint\.com/.*",
        # Google Docs
        r"https?://docs\.google\.com/.*",
        # Adobe PDFs
        r"https?://.*\.pdf",
        # Microsoft Office files
        r"https?://.*\.(doc|docx|xls|xlsx|ppt|pptx)",
        # Image files
        r"https?://.*\.(jpg|jpeg|png|gif|bmp|webp|svg|ico)",
        # Video files
        r"https?://.*\.(mp4|avi|mov|wmv|flv)",
        # Microsoft login
        r"https?://login\.microsoftonline\.com/.*",
        # Google login
        r"https?://accounts\.google\.com/.*",
        # Archives
        r"https?://web\.archive\.org/.*",
        r"https?://archive\..*/.*",  # Block all of archive domains
        r"https?://.*\.webcache\.googleusercontent\.com/.*",  # Any Google cache
        r"https?://cachedview\.nl/.*",
        r"https?://(www\.)?memento\.(.*)/.*",  # Memento framework
        # Social Media (even embeds)
        r"https?://(www\.)?(facebook|twitter|instagram|linkedin|youtube|vimeo)\.com/.*",
        # Specific Hostile Subdomains
        r"https?://(www\.)?blog\..*/.*",  # Any blog subdomain
        r"https?://(www\.)?forums?\..*/.*",  # Any forum subdomain
        r"https?://(www\.)?wiki\..*/.*",  # Any wiki subdomain
        r"https?://(www\.)?news\..*/.*",  # Any news subdomain
        r"https?://(www\.)?events\..*/.*",  # Any events subdomain
        r"https?://(www\.)?calendar\..*/.*",  # Any calendar subdomain
        r"https?://(www\.)?shop\..*/.*",  # Any shop subdomain
        r"https?://(www\.)?store\..*/.*",  # Any store subdomain
        r"https?://(www\.)?jobs\..*/.*",  # Any jobs subdomain
        r"https?://(www\.)?careers\..*/.*",  # Any careers subdomain
        r"https?://(www\.)?donate\..*/.*",  # Any donate subdomain
        # Tracking and Ads
        r".*/utm_.*",  # Google Analytics tracking
        r".*/gclid=.*",  # Google Click Identifier
        r".*/fbclid=.*",  # Facebook Click Identifier
        r".*/ref=.*",  # General referrer tracking
        r".*/ad\..*",  # Ad-related paths
        r".*/advert.*",
        r".*/banner.*",
        r".*/click.*",
        # Authentication and Sessions
        r".*/(login|signin|signup|register|auth)/?.*",
        r".*/session/.*",
        r".*/logout/?.*",
        r".*/password/?.*",
        r".*/token=.*",
        # Files and Media (Aggressive)
        r".*\.(jpg|jpeg|png|gif|bmp|webp|svg|ico|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|mp3|mp4|avi|mov|wmv|flv)$",
        # Feeds
        r".*/feed/?.*",
        r".*/rss/?.*",
        # API Endpoints
        r".*/api/.*",
        r".*/v\d+/.*",  # API versioning
        # Parameters that indicate sorting, filtering, etc.
        r".*/sort=.*",
        r".*/order=.*",
        r".*/filter=.*",
        r".*/page=\d+",
        # User-Specific
        r".*/user/.*",
        r".*/profile/.*",
        # Dates
        r"/\d{4}/\d{2}/\d{2}/.*",
        r"/\d{4}/\d{2}/.*",
        r"/\d{4}/.*",
        # Anything with a query string that is long (likely search or complex filtering)
        r".*\?(.){50,}",
        # Anything with a fragment identifier (used for on-page navigation, often noisy)
        r".*#.*",
        # Common CMS admin paths
        r".*/wp-admin/.*",  # Wordpress
        r".*/admin/.*",  # Generic admin path
        r".*/administrator/.*",  # Joomla admin
        r".*/sites/default/files/.*",  # Drupal files
        # Search Results
        r".*/search-results/.*",
        # Anything with a path segment that looks like a hash (likely a resource identifier)
        r".*/[a-f0-9]{8,}/.*",
        # Anything with a path segment that looks like a UUID
        r".*/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.*",
        # External redirects
        r"https?://out\..*/.*",
        r"https?://go\..*/.*",
        r"https?://click\..*/.*",
        r"https?://exit\..*/.*",
        # Subdomains that are often separate applications
        r"https?://status\..*/.*",
        r"https?://help\..*/.*",
        r"https?://support\..*/.*",
        r"https?://cdn\..*/.*",  # Content Delivery Network
        r"https?://s3\..*/.*",  # Amazon S3
        r"https?://files\..*/.*",  # Files subdomains
        r"https?://api\..*/.*",  # API subdomains
        r"https?://app\..*/.*",  # Application subdomains
        r"https?://static\..*/.*",  # Static assets
        r"https?://assets\..*/.*",  # Assets
        # Exclude known external application or support systems
        r"https?://(?:[\w\-]+\.)?harvard\.service\-now\.com/.*",
        r"https?://(?:[\w\-]+\.)?harvard\.az1\.qualtrics\.com/.*",
        r"https?://(?:[\w\-]+\.)?commonapp\.org/.*",
        r"https?://(?:[\w\-]+\.)?apprenticeships\.ox\.ac\.uk/.*",
        r"https?://(?:[\w\-]+\.)?prod\-transportation\.drupalsites\.harvard\.edu/.*",
        r"https?://(?:[\w\-]+\.)?list\-manage\.com/.*",
        r"https?://(?:[\w\-]+\.)?amazonaws\.com/.*",
        # Exclude pages that include cookie-related toggles in the URL
        r"https?://.*(/@@enable\-cookies|/%40%40enable\-cookies|/@@disable\-cookies|/%40%40disable\-cookies).*",
    ]

    SUSPICIOUS_PATTERNS = [
        r"/calendar/",
        r"/page/\d+",
        r"/p/\d+",
        r"/\d{4}/\d{2}/\d{2}/",  # Date patterns
        r"/tag/",
        r"/tags/",
        r"/author/",
        r"/user/",
        r"/users/",
        r"/comment",
        r"/comments/",
        r"/attachment",
        r"/print/",
        r"/rss",
        r"/feed",
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
    # Cache Settings
    #

    # Whether to use request caching
    USE_CACHE = True

    # Cache expiration time in seconds (24 hours)
    CACHE_EXPIRE_AFTER = 86400

    # Maximum cache size (in MB)
    CACHE_MAX_SIZE = 1000  # 1GB

    # Whether to use compression for cached responses
    CACHE_COMPRESSION = True

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
