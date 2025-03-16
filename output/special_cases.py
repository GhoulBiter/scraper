"""
Special case definitions for university application systems.

This file contains mappings and rules for universities with unique application processes
or those that use specific external application systems.
"""

# Dictionary of known external application systems with their official URLs
EXTERNAL_APPLICATION_SYSTEMS = {
    "ucas": {
        "name": "UCAS (Universities and Colleges Admissions Service)",
        "url": "https://www.ucas.com/apply",
        "description": "The central application service for UK undergraduate programs",
    },
    "common_app": {
        "name": "Common Application",
        "url": "https://apply.commonapp.org/login",
        "description": "Application platform for over 900 colleges and universities, primarily in the US",
    },
    "coalition": {
        "name": "Coalition Application",
        "url": "https://app.coalitionforcollegeaccess.org/",
        "description": "Alternative to Common App, used by about 150 US colleges and universities",
    },
    "uc_application": {
        "name": "University of California Application",
        "url": "https://apply.universityofcalifornia.edu/my-application/login",
        "description": "Central application for all University of California campuses",
    },
    "cal_state_apply": {
        "name": "Cal State Apply",
        "url": "https://www.calstate.edu/apply",
        "description": "Application portal for all California State University campuses",
    },
    "applytexas": {
        "name": "ApplyTexas",
        "url": "https://www.applytexas.org/adappc/gen/c_start.WBX",
        "description": "Application system for Texas public universities and community colleges",
    },
    "ouac": {
        "name": "Ontario Universities' Application Centre",
        "url": "https://www.ouac.on.ca/apply/",
        "description": "Central application service for universities in Ontario, Canada",
    },
    "uac": {
        "name": "Universities Admissions Centre (Australia)",
        "url": "https://www5.uac.edu.au/uacug/",
        "description": "Central admissions for undergraduate study at participating institutions in NSW and ACT, Australia",
    },
    "studylink": {
        "name": "StudyLink (New Zealand)",
        "url": "https://www.studylink.govt.nz/apply/",
        "description": "New Zealand's student loan and allowance application system",
    },
    "uni_assist": {
        "name": "uni-assist (Germany)",
        "url": "https://www.uni-assist.de/en/how-to-apply/",
        "description": "Application service for international students applying to German universities",
    },
}

# Special case mappings for specific universities and domains
UNIVERSITY_SPECIAL_CASES = {
    # UK Universities that use UCAS
    "University of Cambridge": {
        "system": "ucas",
        "note": "All undergraduate applications to Cambridge must be submitted through UCAS",
        "application_portal": "https://www.ucas.com/apply",
        "institution_code": "CAM C05",
    },
    "University of Oxford": {
        "system": "ucas",
        "note": "All undergraduate applications to Oxford must be submitted through UCAS",
        "application_portal": "https://www.ucas.com/apply",
        "institution_code": "OXFORD O33",
    },
    "Imperial College London": {
        "system": "ucas",
        "note": "All undergraduate applications to Imperial must be submitted through UCAS",
        "application_portal": "https://www.ucas.com/apply",
        "institution_code": "IMPERIAL I50",
    },
    "UCL": {
        "system": "ucas",
        "note": "All undergraduate applications to UCL must be submitted through UCAS",
        "application_portal": "https://www.ucas.com/apply",
        "institution_code": "UCL U80",
    },
    # University of California system
    "University of California, Berkeley": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Berkeley", "Berkeley", "Cal"],
    },
    "University of California, Los Angeles": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UCLA"],
    },
    "University of California, San Diego": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UCSD"],
    },
    "University of California, Davis": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Davis", "UCD"],
    },
    "University of California, Irvine": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Irvine", "UCI"],
    },
    "University of California, Santa Barbara": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Santa Barbara", "UCSB"],
    },
    "University of California, Santa Cruz": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Santa Cruz", "UCSC"],
    },
    "University of California, Riverside": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Riverside", "UCR"],
    },
    "University of California, Merced": {
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
        "alternate_names": ["UC Merced", "UCM"],
    },
    # California State University System
    "California State University": {
        "system": "cal_state_apply",
        "note": "All CSU campuses use the same application portal",
        "application_portal": "https://www.calstate.edu/apply",
        "alternate_names": ["Cal State", "CSU"],
    },
    # ApplyTexas universities
    "University of Texas at Austin": {
        "system": "applytexas",
        "note": "UT Austin uses the ApplyTexas application system",
        "application_portal": "https://www.applytexas.org/adappc/gen/c_start.WBX",
        "alternate_names": ["UT Austin", "UT"],
    },
    "Texas A&M University": {
        "system": "applytexas",
        "note": "Texas A&M uses the ApplyTexas application system",
        "application_portal": "https://www.applytexas.org/adappc/gen/c_start.WBX",
        "alternate_names": ["Texas A&M", "TAMU"],
    },
}

# Domain pattern special cases
DOMAIN_PATTERNS = [
    # UK universities (.ac.uk) generally use UCAS for undergraduate applications
    {
        "pattern": r"\.ac\.uk",
        "system": "ucas",
        "note": "UK universities use UCAS for undergraduate applications",
        "application_portal": "https://www.ucas.com/apply",
    },
    # University of California domains
    {
        "pattern": r".*\.berkeley\.edu",
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
    },
    {
        "pattern": r".*\.ucla\.edu",
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
    },
    {
        "pattern": r".*\.ucsd\.edu",
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
    },
    {
        "pattern": r".*\.ucdavis\.edu",
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
    },
    {
        "pattern": r".*\.uci\.edu",
        "system": "uc_application",
        "note": "All UC campuses use the same application portal",
        "application_portal": "https://apply.universityofcalifornia.edu/my-application/login",
    },
    # Common App participating schools often have specific information
    {
        "pattern": r"commonapp\.org",
        "system": "common_app",
        "note": "This refers to the Common Application system used by many US colleges",
        "application_portal": "https://apply.commonapp.org/login",
    },
    # Coalition App
    {
        "pattern": r"coalitionforcollegeaccess\.org",
        "system": "coalition",
        "note": "This refers to the Coalition Application system",
        "application_portal": "https://app.coalitionforcollegeaccess.org/",
    },
]

# Indicators to help identify graduate vs undergraduate pages
GRADUATE_INDICATORS = [
    "graduate",
    "grad",
    "phd",
    "doctoral",
    "master",
    "postgraduate",
    "mba",
    "msc",
    "ma ",
    "ms ",
    "doctorate",
]

UNDERGRADUATE_INDICATORS = [
    "undergraduate",
    "undergrad",
    "freshman",
    "freshmen",
    "first-year",
    "first year",
    "bachelor",
    "transfer",
    "high school",
    "college",
]


def get_special_case_for_university(university_name):
    """Get special case information for a university by name."""
    # Check direct match
    if university_name in UNIVERSITY_SPECIAL_CASES:
        return UNIVERSITY_SPECIAL_CASES[university_name]

    # Check alternate names
    for univ, info in UNIVERSITY_SPECIAL_CASES.items():
        if "alternate_names" in info:
            if university_name in info["alternate_names"]:
                return info

    # No special case found
    return None


def get_special_case_for_domain(url):
    """Get special case information based on URL domain pattern matching."""
    import re

    for pattern_info in DOMAIN_PATTERNS:
        if re.search(pattern_info["pattern"], url, re.IGNORECASE):
            return pattern_info

    return None


def is_undergraduate_page(page):
    """
    Determine if a page is related to undergraduate (not graduate) applications.

    Args:
        page: The application page dictionary

    Returns:
        bool: True if the page is likely for undergraduate applications
    """
    # Skip graduate pages
    title = page.get("title", "").lower()
    url = page.get("url", "").lower()

    # Check for graduate indicators in title or URL
    if any(grad in title for grad in GRADUATE_INDICATORS):
        return False
    if any(grad in url for grad in GRADUATE_INDICATORS):
        return False

    # Check for specific graduate domains
    if "gradadmissions" in url or "graduate.admissions" in url:
        return False

    # Check if it explicitly mentions undergraduate
    if any(ugrad in title for ugrad in UNDERGRADUATE_INDICATORS):
        return True
    if any(ugrad in url for ugrad in UNDERGRADUATE_INDICATORS):
        return True

    # Default to including the page if no graduate indicators found
    return True
