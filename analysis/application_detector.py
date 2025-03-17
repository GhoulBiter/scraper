"""
Unified application page detection with consistent criteria
"""

import re

from models.application_systems import (
    detect_application_system,
)


def is_undergraduate_page(page):
    """
    Determine if a page is related to undergraduate (not graduate) applications.

    Args:
        page (dict): The application page dictionary

    Returns:
        bool: True if the page is likely for undergraduate applications
    """
    # Define indicators to help identify graduate vs undergraduate pages
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

    # Check in AI evaluation if available
    if "ai_evaluation" in page:
        eval_text = page["ai_evaluation"].lower()
        if any(grad in eval_text for grad in GRADUATE_INDICATORS):
            return False
        if any(ugrad in eval_text for ugrad in UNDERGRADUATE_INDICATORS):
            return True

    # Default to including the page if no graduate indicators found
    return True


def categorize_application_page(page, html=None):
    """
    Categorize an application page by type (direct, external, info).

    Args:
        page (dict): The application page dictionary
        html (str, optional): HTML content if not included in page

    Returns:
        dict: Updated page with categorization
    """
    # If category or application_type is already set, return as is
    if page.get("category") and page.get("application_type"):
        return page

    html_content = html or page.get("html_snippet", "")
    url = page.get("url", "")
    title = page.get("title", "")

    result = page.copy()
    is_actual_app = False
    category = 3  # Default to information only
    application_type = "information_only"

    # Check for direct application form indicators
    direct_app_indicators = [
        r"<form[^>]*>",
        r"login\s*form",
        r"application\s*form",
        r"apply\s*now\s*button",
        r"start\s*(your|my|the)\s*application",
        r"submit\s*application",
        r"application\s*login",
        r"login\s*to\s*(your|my|the)\s*application",
        r"create\s*an\s*account",
        r"sign\s*up\s*to\s*apply",
    ]

    # First check for direct application
    direct_form_score = 0
    for indicator in direct_app_indicators:
        if re.search(indicator, html_content, re.IGNORECASE):
            direct_form_score += 1

    # Check for actual form elements
    if re.search(
        r'<input[^>]*type=["\'](?:text|email|password)["\'][^>]*>',
        html_content,
        re.IGNORECASE,
    ):
        direct_form_score += 2

    if re.search(
        r'<button[^>]*type=["\']submit["\'][^>]*>', html_content, re.IGNORECASE
    ):
        direct_form_score += 1

    # Check for external system
    external_system = detect_application_system(
        url=url, html_content=html_content, university_name=page.get("university", "")
    )

    # Determine category based on scores and checks
    if direct_form_score >= 3:
        # This is a direct application
        is_actual_app = True
        category = 1
        application_type = "direct_application"

    elif external_system:
        # This is an external system reference
        is_actual_app = True
        category = 2
        application_type = "external_application_reference"

        # Add external system info
        result["external_application_systems"] = [external_system]

    elif direct_form_score > 0:
        # This might be an application instructions page
        is_actual_app = True
        category = 2  # Application portal reference
        application_type = "application_instructions"

    # Update result with categorization
    result["is_actual_application"] = is_actual_app
    result["category"] = category
    result["application_type"] = application_type

    return result


def extract_institution_codes(html):
    """
    Extract institution codes from HTML content.

    Args:
        html (str): HTML content to analyze

    Returns:
        dict: Dictionary with extracted codes
    """
    if not html:
        return {}

    results = {"institution_code": None, "program_code": None}

    html_lower = html.lower()

    # Look for institution codes (common formats)
    inst_code_patterns = [
        r"institution code:?\s*([A-Z0-9]{4,6})",
        r"college code:?\s*([A-Z0-9]{4,6})",
        r"university code:?\s*([A-Z0-9]{4,6})",
        r"ucas code:?\s*([A-Z0-9]{4,6})",
        r"school code:?\s*([A-Z0-9]{4,6})",
    ]

    for pattern in inst_code_patterns:
        code_match = re.search(pattern, html_lower)
        if code_match:
            results["institution_code"] = code_match.group(1).upper()
            break

    # Look for program codes
    prog_code_patterns = [
        r"program code:?\s*([A-Z0-9]{3,8})",
        r"course code:?\s*([A-Z0-9]{3,8})",
        r"major code:?\s*([A-Z0-9]{3,8})",
    ]

    for pattern in prog_code_patterns:
        code_match = re.search(pattern, html_lower)
        if code_match:
            results["program_code"] = code_match.group(1).upper()
            break

    return results


def extract_education_level(html, url="", title=""):
    """
    Extract the targeted education level from the page content.

    Args:
        html (str): HTML content
        url (str, optional): Page URL
        title (str, optional): Page title

    Returns:
        str: Education level ("undergraduate", "graduate", "doctoral", or "unknown")
    """
    # Define indicator patterns
    EDUCATION_LEVEL_PATTERNS = {
        "undergraduate": [
            r"undergraduate",
            r"bachelor",
            r"freshman",
            r"freshmen",
            r"first.year",
            r"transfer student",
            r"high school",
        ],
        "graduate": [
            r"graduate",
            r"master",
            r"ma program",
            r"ms program",
            r"msc",
            r"postgraduate",
        ],
        "doctoral": [
            r"doctoral",
            r"phd",
            r"doctorate",
            r"research degree",
        ],
    }

    # Combine all content for analysis
    combined_text = f"{url} {title} {html}"[:10000].lower()

    # Count occurrences of each level's indicators
    scores = {"undergraduate": 0, "graduate": 0, "doctoral": 0}

    for level, patterns in EDUCATION_LEVEL_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, combined_text)
            scores[level] += len(matches)

    # Check if URL or title has direct indicators - these get extra weight
    for level, patterns in EDUCATION_LEVEL_PATTERNS.items():
        combined_title_url = f"{url} {title}".lower()
        for pattern in patterns:
            if re.search(pattern, combined_title_url):
                scores[level] += 5  # Extra weight for indicators in URL/title

    # Determine the most likely level
    if max(scores.values()) == 0:
        return "unknown"

    # Return the level with the highest score
    return max(scores.items(), key=lambda x: x[1])[0]
