"""
Page analysis utilities for identifying application pages
"""

import re
from urllib.parse import urlparse

from loguru import logger
from config import Config
from models.application_systems import EXTERNAL_APPLICATION_SYSTEMS


def extract_title(html):
    """Extract page title from HTML with Unicode support."""

    if not html:
        return ""

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
    )
    if title_match:
        title = title_match.group(1).strip()
        # Clean up common HTML entities
        title = re.sub(r"&amp;", "&", title)
        title = re.sub(r"&lt;", "<", title)
        title = re.sub(r"&gt;", ">", title)
        title = re.sub(r"&quot;", '"', title)
        title = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), title)
        return title
    return ""


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
            f"<(a|button)[^>]*>(.*?{pattern}.*?)</(a|button)>", html, re.IGNORECASE
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

    # Check for external application system references
    external_system_found = False
    external_system_name = None
    for system, identifiers in EXTERNAL_APPLICATION_SYSTEMS.items():
        for identifier in identifiers:
            if identifier in html.lower():
                external_system_found = True
                external_system_name = system
                reasons.append(f"References external application system: {identifier}")
                score += 4
                break
        if external_system_found:
            break

    # Check for university-specific application portal references
    portal_patterns = [
        r"my\s*\w+\s*application",  # "My Cambridge Application", "My Stanford Application"
        r"\w+\s*application\s*portal",  # "University Application Portal"
        r"application\s*system",
        r"applicant\s*portal",
        r"application\s*portal",
        r"application\s*account",
        r"application\s*platform",
        r"apply\s*online",
        r"online\s*application\s*(form|system)",
    ]

    for pattern in portal_patterns:
        if re.search(pattern, html.lower()):
            reasons.append(
                f"Contains reference to application portal: {re.search(pattern, html.lower()).group(0)}"
            )
            score += 3

    # Check for application process instructions
    instruction_patterns = [
        r"(how|steps)\s*to\s*apply",
        r"application\s*(process|procedure|instructions)",
        r"application\s*(deadline|due date)",
        r"(submit|complete)\s*your\s*application",
        r"after\s*(you|submitting)\s*(submit|application)",
        r"before\s*(you|submitting)\s*(submit|application)",
        r"(application|institution|college|program)\s*code",
        r"application\s*checklist",
    ]

    for pattern in instruction_patterns:
        if re.search(pattern, html.lower()):
            reasons.append(
                f"Contains application instructions: {re.search(pattern, html.lower()).group(0)}"
            )
            score += 2

    # Return based on confidence score
    return score >= 3, reasons
