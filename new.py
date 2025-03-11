import threading
import queue
import time
import os
import json
import logging
import re
import csv
from datetime import datetime
from urllib.parse import urljoin, urlparse
import asyncio
import aiohttp
from scrapy.http import TextResponse
from playwright.async_api import async_playwright
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from dotenv import load_dotenv
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("crawler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


# Configuration module
class Config:
    # List of seed universities to crawl
    SEED_UNIVERSITIES = [
        {"name": "MIT", "base_url": "https://www.mit.edu", "domain": "mit.edu"},
        {
            "name": "Stanford",
            "base_url": "https://www.stanford.edu",
            "domain": "stanford.edu",
        },
        # Add more universities as needed
    ]

    # Common settings
    MAX_DEPTH = 7
    NUM_WORKERS = 4
    REQUEST_DELAY = 1  # Time in seconds to wait between requests (politeness)

    # Enhanced keyword sets for application pages
    KEYWORDS = {
        # General application terms
        "general": [
            "bachelor",
            "undergraduate",
            "apply",
            "application",
            "admission",
            "admissions",
            "major",
            "enroll",
            "register",
            "degree",
            "program",
            "first-year",
            "freshman",
            "new student",
            "prospective",
        ],
        # Action-oriented terms
        "action": [
            "apply now",
            "start application",
            "begin application",
            "submit application",
            "create account",
            "sign up",
            "register now",
            "get started",
            "start here",
            "apply online",
            "apply today",
            "how to apply",
        ],
        # URL patterns that often indicate application-related pages
        "url_patterns": [
            "/apply",
            "/application",
            "/admission",
            "/admissions",
            "/undergraduate",
            "/students/prospective",
            "/future-students",
        ],
    }

    # Portal detection indicators
    PORTAL_INDICATORS = {
        # Form field types that suggest a portal/login
        "fields": ["password", "username", "login", "email"],
        # Button/text indicators for portals
        "buttons": [
            "sign in",
            "log in",
            "login",
            "create account",
            "register",
            "continue application",
            "start application",
            "common app",
        ],
        # Portal-specific phrases
        "phrases": [
            "return to your application",
            "continue your application",
            "check status",
            "application status",
            "application portal",
            "log in to apply",
            "create an account to apply",
        ],
    }

    # Context extraction settings
    CONTEXT_RADIUS = 100  # Characters to extract before and after the match


# Shared data structures and locks
url_queue = queue.Queue()
visited = {}  # Changed to dict: {domain: set(urls)} to manage per-university
visited_lock = threading.Lock()

application_links = (
    {}
)  # Mapping: {normalized_link: {"page_url": url, "university": name, "context": context}}
application_links_lock = threading.Lock()

forms_found = []  # List of dicts with form info
forms_found_lock = threading.Lock()

# Entry point classification results
entry_points = []  # List of classified entry points
entry_points_lock = threading.Lock()

# Additional data structures for async crawling
urls_needing_js = set()  # URLs that need JavaScript rendering
url_rendering_lock = threading.Lock()

# Semaphore for controlling concurrency
max_concurrent_requests = 20  # Adjust based on your system's capability


def normalize_url(url):
    """Normalize a URL by removing its fragment (the part after #)."""
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="").geturl()
    return normalized


def get_domain(url):
    """Extract the domain from a URL."""
    return urlparse(url).netloc


def url_has_pattern(url):
    """Check if URL contains patterns typical of application pages."""
    for pattern in Config.KEYWORDS["url_patterns"]:
        if pattern in url:
            return True
    return False


async def setup_playwright():
    """Initialize and return a playwright browser instance."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    return playwright, browser


async def close_playwright(playwright, browser):
    """Close playwright browser and playwright."""
    await browser.close()
    await playwright.stop()


def extract_context(element, page_source):
    """
    Extract text context surrounding an element.

    Args:
        element: The Selenium WebElement
        page_source: The full HTML source of the page

    Returns:
        A string containing text context around the element
    """
    try:
        # Try to get the outer HTML of the element
        outer_html = element.get_attribute("outerHTML")
        if not outer_html:
            return "Context extraction failed: No HTML"

        # Find the position of this element in the page source
        start_pos = page_source.find(outer_html)
        if start_pos == -1:
            return "Context extraction failed: Element not found in source"

        # Extract text before and after the element
        radius = Config.CONTEXT_RADIUS
        context_start = max(0, start_pos - radius)
        context_end = min(len(page_source), start_pos + len(outer_html) + radius)

        context = page_source[context_start:context_end]

        # Clean up the context (remove excessive whitespace and HTML tags)
        context = re.sub(r"<[^>]+>", " ", context)  # Remove HTML tags
        context = re.sub(r"\s+", " ", context).strip()  # Normalize whitespace

        return context
    except Exception as e:
        logger.error(f"Error extracting context: {e}")
        return "Context extraction failed"


def analyze_form_type(form_element):
    """
    Analyze a form to determine if it's a login/portal form or a direct application form.

    Args:
        form_element: The Selenium WebElement for the form

    Returns:
        A tuple of (form_type, evidence) where form_type is one of:
        - 'portal': Likely a login or account creation form
        - 'direct': Likely a direct application form
        - 'unknown': Cannot determine
    """
    try:
        form_html = form_element.get_attribute("outerHTML")
        evidence = []

        # Check for portal indicators in form fields
        password_fields = form_element.find_elements(
            By.XPATH, ".//input[@type='password']"
        )
        if password_fields:
            evidence.append("Contains password field")

        # Look for common input field names/types that suggest a portal
        for field_indicator in Config.PORTAL_INDICATORS["fields"]:
            fields = form_element.find_elements(
                By.XPATH,
                f".//input[contains(@name, '{field_indicator}') or contains(@id, '{field_indicator}') or contains(@placeholder, '{field_indicator}')]",
            )
            if fields:
                evidence.append(f"Contains {field_indicator} field")

        # Check for portal-related button text
        for button_text in Config.PORTAL_INDICATORS["buttons"]:
            buttons = form_element.find_elements(
                By.XPATH,
                f".//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text}')]",
            )
            if buttons:
                evidence.append(f"Contains '{button_text}' button")

        # Check form for phrases that suggest a portal
        form_text = form_element.text.lower()
        for phrase in Config.PORTAL_INDICATORS["phrases"]:
            if phrase.lower() in form_text:
                evidence.append(f"Contains phrase '{phrase}'")

        # Check the number of fields - portals typically have fewer fields
        input_fields = form_element.find_elements(By.XPATH, ".//input")
        if len(input_fields) <= 3:
            evidence.append(f"Simple form with only {len(input_fields)} fields")
        elif len(input_fields) > 10:
            evidence.append(f"Complex form with {len(input_fields)} fields")

        # Make a determination based on evidence
        if evidence:
            # More sophisticated logic could be implemented here
            # For now, if there's evidence of a portal, classify as such
            portal_evidence = [
                e
                for e in evidence
                if any(
                    indicator in e.lower()
                    for indicator in [
                        "password",
                        "login",
                        "sign in",
                        "log in",
                        "account",
                    ]
                )
            ]

            if portal_evidence:
                return ("portal", evidence)
            elif len(input_fields) > 8:
                return (
                    "direct",
                    evidence
                    + ["Form has many input fields suggesting direct application"],
                )
            else:
                return ("unknown", evidence)
        else:
            return ("unknown", ["No clear indicators found"])

    except Exception as e:
        logger.error(f"Error analyzing form type: {e}")
        return ("unknown", [f"Error during analysis: {str(e)}"])


async def process_html(url, html_content, depth, university):
    """
    Process HTML content without JavaScript rendering.

    Args:
        url: The URL being processed
        html_content: The HTML content of the page
        depth: Current crawl depth
        university: Dictionary containing university information
    """
    normalized_url = normalize_url(url)
    university_domain = university["domain"]

    # Create a Scrapy TextResponse object for easier parsing
    response = TextResponse(url=url, body=html_content, encoding="utf-8")

    # Extract page title
    page_title = response.xpath("//title/text()").get() or ""

    # Check if this page likely needs JavaScript rendering
    needs_js = False

    # Simple heuristics to detect if JavaScript is needed:
    # 1. Check for forms with no action attribute
    forms_no_action = response.xpath("//form[not(@action)]").getall()
    if forms_no_action:
        needs_js = True

    # 2. Check for minimal content in the body
    body_text = " ".join(response.xpath("//body//text()").getall())
    if len(body_text.strip()) < 500 and response.xpath("//script").getall():
        needs_js = True

    # 3. Check for React/Angular/Vue patterns
    if response.xpath(
        "//*[@ng-app or @ng-controller or @v-app or @data-reactroot]"
    ).get():
        needs_js = True

    if needs_js:
        # Mark this URL for JavaScript rendering
        with url_rendering_lock:
            urls_needing_js.add(normalized_url)
        return

    # Process forms on the page
    forms = response.xpath("//form")
    for form in forms:
        form_action = form.xpath("@action").get() or ""
        if not form_action:
            continue

        full_form_url = (
            form_action if form_action.startswith("http") else urljoin(url, form_action)
        )
        form_html = form.get()

        # Extract context (simplified for non-Selenium approach)
        form_context = extract_context_from_html(form.get(), html_content)

        # Analyze form type using regex-based patterns instead of DOM analysis
        form_type, evidence = analyze_form_type_html(form.get())

        form_data = {
            "form_url": full_form_url,
            "page_url": normalized_url,
            "page_title": page_title,
            "university": university["name"],
            "form_html": form_html,
            "context": form_context,
            "form_type": form_type,
            "evidence": evidence,
            "js_rendered": False,
        }

        with forms_found_lock:
            forms_found.append(form_data)

        # If this appears to be an application-related form, add to entry points
        if any(
            keyword in normalized_url.lower()
            or keyword in page_title.lower()
            or keyword in form_context.lower()
            for keyword in Config.KEYWORDS["general"]
        ):

            with entry_points_lock:
                entry_points.append(
                    {
                        "type": "form",
                        "entry_type": form_type,
                        "url": normalized_url,
                        "form_action": full_form_url,
                        "university": university["name"],
                        "evidence": evidence,
                        "context": form_context[:200],
                        "title": page_title,
                        "js_rendered": False,
                    }
                )

            logger.info(
                f"Found form: {full_form_url} on page: {normalized_url} (Type: {form_type})"
            )

    # Extract links
    anchors = response.xpath("//a[@href]")
    for anchor in anchors:
        href = anchor.xpath("@href").get()
        text = anchor.xpath("string(.)").get() or ""

        if not href:
            continue

        full_url = href if href.startswith("http") else urljoin(url, href)
        normalized_full_url = normalize_url(full_url)
        parsed_url = urlparse(normalized_full_url)

        # Check if the URL belongs to the university domain
        if university_domain not in parsed_url.netloc:
            continue

        # Check for keywords in text and URL
        is_application_link = False
        match_reason = []

        # Check general keywords
        if any(keyword in text.lower() for keyword in Config.KEYWORDS["general"]):
            is_application_link = True
            match_reason.append("General keyword in link text")

        # Check action keywords
        if any(action in text.lower() for action in Config.KEYWORDS["action"]):
            is_application_link = True
            match_reason.append("Action keyword in link text")

        # Check URL patterns
        if url_has_pattern(normalized_full_url):
            is_application_link = True
            match_reason.append("URL pattern match")

        # If it's an application link, extract context and store
        if is_application_link:
            context = extract_context_from_html(anchor.get(), html_content)

            # Determine if this is likely a portal link
            is_portal = False
            portal_evidence = []

            # Check for portal indicators in link text and surrounding context
            for phrase in (
                Config.PORTAL_INDICATORS["phrases"]
                + Config.PORTAL_INDICATORS["buttons"]
            ):
                if phrase.lower() in text.lower() or phrase.lower() in context.lower():
                    is_portal = True
                    portal_evidence.append(f"Contains phrase '{phrase}'")

            entry_type = "portal" if is_portal else "unknown"

            with application_links_lock:
                if normalized_full_url not in application_links:
                    application_links[normalized_full_url] = {
                        "page_url": normalized_url,
                        "page_title": page_title,
                        "university": university["name"],
                        "link_text": text,
                        "context": context,
                        "match_reason": match_reason,
                        "entry_type": entry_type,
                        "portal_evidence": portal_evidence,
                        "js_rendered": False,
                    }

                    # Add to entry points
                    with entry_points_lock:
                        entry_points.append(
                            {
                                "type": "link",
                                "entry_type": entry_type,
                                "url": normalized_full_url,
                                "source_url": normalized_url,
                                "university": university["name"],
                                "link_text": text,
                                "evidence": match_reason + portal_evidence,
                                "context": context[:200],
                                "title": page_title,
                                "js_rendered": False,
                            }
                        )

                    logger.info(
                        f"Found potential application link: {normalized_full_url} on page: {normalized_url}"
                    )
                    logger.info(f"Match reason: {', '.join(match_reason)}")
                    if portal_evidence:
                        logger.info(f"Portal evidence: {', '.join(portal_evidence)}")

        # Add new URL to the queue if it hasn't been visited
        with visited_lock:
            if (
                university_domain not in visited
                or normalized_full_url not in visited[university_domain]
            ):
                url_queue.put((normalized_full_url, depth - 1, university))


async def process_with_playwright(url, depth, university, browser):
    """
    Process a URL using Playwright for JavaScript rendering.

    Args:
        url: The URL to crawl
        depth: Current crawl depth
        university: Dictionary containing university information
        browser: The Playwright browser instance
    """
    normalized_url = normalize_url(url)
    university_domain = university["domain"]

    # Mark as visited
    with visited_lock:
        if university_domain not in visited:
            visited[university_domain] = set()
        visited[university_domain].add(normalized_url)

    try:
        # Create a new page
        page = await browser.new_page()

        # Set timeout
        page.set_default_timeout(15000)

        # Navigate to the URL
        await page.goto(url, wait_until="networkidle")

        # Get the current URL (in case of redirects)
        current_url = page.url
        normalized_current_url = normalize_url(current_url)

        # Get page title
        page_title = await page.title()

        # Get page content
        page_source = await page.content()

        # Process forms on the page
        forms = await page.query_selector_all("form")
        logger.info(
            f"Found {len(forms)} forms on {normalized_current_url} (JS rendered)"
        )

        for form in forms:
            try:
                form_action = await form.get_attribute("action") or ""
                if not form_action:
                    continue

                full_form_url = (
                    form_action
                    if form_action.startswith("http")
                    else urljoin(current_url, form_action)
                )
                form_html = await form.evaluate("el => el.outerHTML")

                # Get form element content for context extraction
                form_context = await form.evaluate("el => el.textContent")

                # Analyze form type
                form_type, evidence = await analyze_form_type_playwright(form)

                form_data = {
                    "form_url": full_form_url,
                    "page_url": normalized_current_url,
                    "page_title": page_title,
                    "university": university["name"],
                    "form_html": form_html,
                    "context": form_context,
                    "form_type": form_type,
                    "evidence": evidence,
                    "js_rendered": True,
                }

                with forms_found_lock:
                    forms_found.append(form_data)

                # If this appears to be an application-related form, add to entry points
                if any(
                    keyword in normalized_current_url.lower()
                    or keyword in page_title.lower()
                    or keyword in form_context.lower()
                    for keyword in Config.KEYWORDS["general"]
                ):

                    with entry_points_lock:
                        entry_points.append(
                            {
                                "type": "form",
                                "entry_type": form_type,
                                "url": normalized_current_url,
                                "form_action": full_form_url,
                                "university": university["name"],
                                "evidence": evidence,
                                "context": form_context[:200],
                                "title": page_title,
                                "js_rendered": True,
                            }
                        )

                    logger.info(
                        f"Found form: {full_form_url} on page: {normalized_current_url} (Type: {form_type}, JS rendered)"
                    )
            except Exception as e:
                logger.error(f"Error processing form on {normalized_current_url}: {e}")

        # Extract and process anchor tags
        anchors = await page.query_selector_all("a[href]")
        logger.info(
            f"Found {len(anchors)} anchors on {normalized_current_url} (JS rendered)"
        )

        for a in anchors:
            try:
                href = await a.get_attribute("href")
                text = await a.text_content()

                if not href:
                    continue

                full_url = (
                    href if href.startswith("http") else urljoin(current_url, href)
                )
                normalized_full_url = normalize_url(full_url)
                parsed_url = urlparse(normalized_full_url)

                # Check if the URL belongs to the university domain
                if university_domain not in parsed_url.netloc:
                    continue

                # Check for keywords in text and URL
                is_application_link = False
                match_reason = []

                # Check general keywords
                if any(
                    keyword in text.lower() for keyword in Config.KEYWORDS["general"]
                ):
                    is_application_link = True
                    match_reason.append("General keyword in link text")

                # Check action keywords
                if any(action in text.lower() for action in Config.KEYWORDS["action"]):
                    is_application_link = True
                    match_reason.append("Action keyword in link text")

                # Check URL patterns
                if url_has_pattern(normalized_full_url):
                    is_application_link = True
                    match_reason.append("URL pattern match")

                # If it's an application link, extract context and store
                if is_application_link:
                    # Get element HTML for context
                    element_html = await a.evaluate("el => el.outerHTML")
                    context = await extract_context_playwright(a, page_source)

                    # Determine if this is likely a portal link
                    is_portal = False
                    portal_evidence = []

                    # Check for portal indicators in link text and surrounding context
                    for phrase in (
                        Config.PORTAL_INDICATORS["phrases"]
                        + Config.PORTAL_INDICATORS["buttons"]
                    ):
                        if (
                            phrase.lower() in text.lower()
                            or phrase.lower() in context.lower()
                        ):
                            is_portal = True
                            portal_evidence.append(f"Contains phrase '{phrase}'")

                    entry_type = "portal" if is_portal else "unknown"

                    with application_links_lock:
                        if normalized_full_url not in application_links:
                            application_links[normalized_full_url] = {
                                "page_url": normalized_current_url,
                                "page_title": page_title,
                                "university": university["name"],
                                "link_text": text,
                                "context": context,
                                "match_reason": match_reason,
                                "entry_type": entry_type,
                                "portal_evidence": portal_evidence,
                                "js_rendered": True,
                            }

                            # Add to entry points
                            with entry_points_lock:
                                entry_points.append(
                                    {
                                        "type": "link",
                                        "entry_type": entry_type,
                                        "url": normalized_full_url,
                                        "source_url": normalized_current_url,
                                        "university": university["name"],
                                        "link_text": text,
                                        "evidence": match_reason + portal_evidence,
                                        "context": context[:200],
                                        "title": page_title,
                                        "js_rendered": True,
                                    }
                                )

                            logger.info(
                                f"Found potential application link: {normalized_full_url} on page: {normalized_current_url} (JS rendered)"
                            )
                            logger.info(f"Match reason: {', '.join(match_reason)}")
                            if portal_evidence:
                                logger.info(
                                    f"Portal evidence: {', '.join(portal_evidence)}"
                                )

                # Add new URL to the queue if it hasn't been visited
                with visited_lock:
                    if (
                        university_domain not in visited
                        or normalized_full_url not in visited[university_domain]
                    ):
                        url_queue.put((normalized_full_url, depth - 1, university))
            except Exception as e:
                logger.error(f"Error processing link on {normalized_current_url}: {e}")

        await page.close()
    except Exception as e:
        logger.error(f"Error loading {url} with Playwright: {e}")


def extract_context_from_html(element_html, page_html):
    """
    Extract text context surrounding an HTML element without using Selenium.

    Args:
        element_html: The HTML string of the element
        page_html: The full HTML string of the page

    Returns:
        A string containing text context around the element
    """
    try:
        if not element_html:
            return "Context extraction failed: No HTML"

        # Find the position of this element in the page source
        start_pos = page_html.find(element_html)
        if start_pos == -1:
            return "Context extraction failed: Element not found in source"

        # Extract text before and after the element
        radius = Config.CONTEXT_RADIUS
        context_start = max(0, start_pos - radius)
        context_end = min(len(page_html), start_pos + len(element_html) + radius)

        context = page_html[context_start:context_end]

        # Clean up the context (remove excessive whitespace and HTML tags)
        context = re.sub(r"<[^>]+>", " ", context)  # Remove HTML tags
        context = re.sub(r"\s+", " ", context).strip()  # Normalize whitespace

        return context
    except Exception as e:
        logger.error(f"Error extracting context from HTML: {e}")
        return "Context extraction failed"


def analyze_form_type_html(form_html):
    """
    Analyze a form's HTML to determine if it's a login/portal form or a direct application form.

    Args:
        form_html: The HTML string of the form element

    Returns:
        A tuple of (form_type, evidence)
    """
    evidence = []

    # Check for password fields
    if 'type="password"' in form_html.lower():
        evidence.append("Contains password field")

    # Look for common input field names/types that suggest a portal
    for field_indicator in Config.PORTAL_INDICATORS["fields"]:
        field_pattern = f'name="{field_indicator}"|id="{field_indicator}"|placeholder="{field_indicator}"'
        if re.search(field_pattern, form_html.lower()):
            evidence.append(f"Contains {field_indicator} field")

    # Check for portal-related button text
    for button_text in Config.PORTAL_INDICATORS["buttons"]:
        if button_text.lower() in form_html.lower():
            evidence.append(f"Contains '{button_text}' button")

    # Count input fields
    input_fields = re.findall(r"<input", form_html.lower())
    if len(input_fields) <= 3:
        evidence.append(f"Simple form with only {len(input_fields)} fields")
    elif len(input_fields) > 10:
        evidence.append(f"Complex form with {len(input_fields)} fields")

    # Make a determination based on evidence
    if evidence:
        portal_evidence = [
            e
            for e in evidence
            if any(
                indicator in e.lower()
                for indicator in ["password", "login", "sign in", "log in", "account"]
            )
        ]

        if portal_evidence:
            return ("portal", evidence)
        elif len(input_fields) > 8:
            return (
                "direct",
                evidence + ["Form has many input fields suggesting direct application"],
            )
        else:
            return ("unknown", evidence)
    else:
        return ("unknown", ["No clear indicators found"])


async def analyze_form_type_playwright(form):
    """
    Analyze a form using Playwright to determine if it's a login/portal form or a direct application form.

    Args:
        form: The Playwright ElementHandle for the form

    Returns:
        A tuple of (form_type, evidence)
    """
    evidence = []

    # Check for password fields
    password_fields = await form.query_selector_all('input[type="password"]')
    if password_fields:
        evidence.append("Contains password field")

    # Look for common input field names/types that suggest a portal
    for field_indicator in Config.PORTAL_INDICATORS["fields"]:
        fields = await form.query_selector_all(
            f'input[name*="{field_indicator}"], input[id*="{field_indicator}"], input[placeholder*="{field_indicator}"]'
        )
        if fields:
            evidence.append(f"Contains {field_indicator} field")

    # Check for portal-related button text
    for button_text in Config.PORTAL_INDICATORS["buttons"]:
        button_selector = f'button:text-matches("{button_text}", "i")'
        buttons = await form.query_selector_all(button_selector)
        if buttons:
            evidence.append(f"Contains '{button_text}' button")

    # Get the form text for phrase analysis
    form_text = await form.evaluate("el => el.textContent")
    form_text = form_text.lower() if form_text else ""

    # Check form for phrases that suggest a portal
    for phrase in Config.PORTAL_INDICATORS["phrases"]:
        if phrase.lower() in form_text:
            evidence.append(f"Contains phrase '{phrase}'")

    # Count input fields
    input_fields = await form.query_selector_all("input")
    if len(input_fields) <= 3:
        evidence.append(f"Simple form with only {len(input_fields)} fields")
    elif len(input_fields) > 10:
        evidence.append(f"Complex form with {len(input_fields)} fields")

    # Make a determination based on evidence
    if evidence:
        portal_evidence = [
            e
            for e in evidence
            if any(
                indicator in e.lower()
                for indicator in ["password", "login", "sign in", "log in", "account"]
            )
        ]

        if portal_evidence:
            return ("portal", evidence)
        elif len(input_fields) > 8:
            return (
                "direct",
                evidence + ["Form has many input fields suggesting direct application"],
            )
        else:
            return ("unknown", evidence)
    else:
        return ("unknown", ["No clear indicators found"])


async def extract_context_playwright(element, page_source):
    """
    Extract text context surrounding an element using Playwright.

    Args:
        element: The Playwright ElementHandle
        page_source: The full HTML content of the page

    Returns:
        A string containing text context around the element
    """
    try:
        # Get the outer HTML of the element
        outer_html = await element.evaluate("el => el.outerHTML")
        if not outer_html:
            return "Context extraction failed: No HTML"

        # Find the position of this element in the page source
        start_pos = page_source.find(outer_html)
        if start_pos == -1:
            return "Context extraction failed: Element not found in source"

        # Extract text before and after the element
        radius = Config.CONTEXT_RADIUS
        context_start = max(0, start_pos - radius)
        context_end = min(len(page_source), start_pos + len(outer_html) + radius)

        context = page_source[context_start:context_end]

        # Clean up the context (remove excessive whitespace and HTML tags)
        context = re.sub(r"<[^>]+>", " ", context)  # Remove HTML tags
        context = re.sub(r"\s+", " ", context).strip()  # Normalize whitespace

        return context
    except Exception as e:
        logger.error(f"Error extracting context with Playwright: {e}")
        return "Context extraction failed"


async def crawl_worker(semaphore, session):
    """
    Asynchronous worker function to process URLs from the queue.

    Args:
        semaphore: Asyncio semaphore to control concurrency
        session: aiohttp ClientSession for HTTP requests
    """
    while True:
        try:
            # Get a URL from the queue (non-blocking)
            try:
                url, depth, university = url_queue.get_nowait()
            except queue.Empty:
                # No more URLs to process
                return

            # Skip if we've already visited this URL
            normalized_url = normalize_url(url)
            university_domain = university["domain"]

            with visited_lock:
                if (
                    university_domain in visited
                    and normalized_url in visited[university_domain]
                ):
                    url_queue.task_done()
                    continue

                # Mark as visited
                if university_domain not in visited:
                    visited[university_domain] = set()
                visited[university_domain].add(normalized_url)

            # Process the URL
            logger.info(f"Processing {url} at depth {depth} for {university['name']}")

            # Apply politeness delay
            await asyncio.sleep(Config.REQUEST_DELAY)

            # Use the semaphore to limit concurrent requests
            async with semaphore:
                try:
                    # Make the request
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            html_content = await response.text()

                            # Process the page's HTML content
                            await process_html(url, html_content, depth, university)

                        else:
                            logger.warning(
                                f"Got status code {response.status} for {url}"
                            )
                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")

            url_queue.task_done()
        except Exception as e:
            logger.error(f"Unexpected error in worker: {e}")
            try:
                url_queue.task_done()
            except:
                pass


def classify_entry_point(data):
    """
    Uses the OpenAI API to classify an entry point as a portal or direct application form.

    Args:
        data: Dictionary containing entry point data

    Returns:
        A dictionary with classification results
    """
    # Construct the prompt based on whether it's a form or link
    if data["type"] == "form":
        prompt = (
            f"Analyze the following information about a web form found on a university website.\n\n"
            f"University: {data['university']}\n"
            f"Page Title: {data['title']}\n"
            f"Form URL: {data['url']}\n"
            f"Form Action: {data['form_action']}\n"
            f"Context around the form: {data['context']}\n\n"
            f"Evidence found: {', '.join(data['evidence'])}\n\n"
            f"Based on this information, classify this form into one of these categories:\n"
            f"1. APPLICATION PORTAL: A login/signup page or portal that leads to an application system\n"
            f"2. DIRECT APPLICATION FORM: A form that directly collects application information\n"
            f"3. UNRELATED: Not related to undergraduate applications\n\n"
            f"Provide your classification with a brief explanation."
        )
    else:  # It's a link
        prompt = (
            f"Analyze the following information about a link found on a university website.\n\n"
            f"University: {data['university']}\n"
            f"Link Text: {data['link_text']}\n"
            f"Link URL: {data['url']}\n"
            f"Found on Page: {data['source_url']}\n"
            f"Context around the link: {data['context']}\n\n"
            f"Evidence found: {', '.join(data['evidence'])}\n\n"
            f"Based on this information, classify this link into one of these categories:\n"
            f"1. APPLICATION PORTAL: Likely leads to a login/signup page or portal for applications\n"
            f"2. DIRECT APPLICATION: Likely leads to a direct application form\n"
            f"3. INFORMATION PAGE: Contains information about applying but not an actual form\n"
            f"4. UNRELATED: Not related to undergraduate applications\n\n"
            f"Provide your classification with a brief explanation."
        )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that analyzes university website elements to determine if they are application forms, portals, or information pages.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        classification_result = response.choices[0].message.content

        # Extract the main classification category
        if "APPLICATION PORTAL" in classification_result:
            main_category = "APPLICATION PORTAL"
        elif "DIRECT APPLICATION" in classification_result:
            main_category = "DIRECT APPLICATION"
        elif "INFORMATION PAGE" in classification_result:
            main_category = "INFORMATION PAGE"
        elif "UNRELATED" in classification_result:
            main_category = "UNRELATED"
        else:
            main_category = "UNDETERMINED"

        return {
            "id": id(data),  # Use object ID as a unique identifier
            "university": data["university"],
            "url": data["url"],
            "type": data["type"],
            "nlp_classification": main_category,
            "full_analysis": classification_result,
            "rule_based_classification": data["entry_type"],
            "evidence": data["evidence"],
        }
    except Exception as e:
        logger.error(f"Error during classification for entry point {data['url']}: {e}")
        return {
            "id": id(data),
            "university": data["university"],
            "url": data["url"],
            "type": data["type"],
            "nlp_classification": "ERROR",
            "full_analysis": f"Classification error: {str(e)}",
            "rule_based_classification": data["entry_type"],
            "evidence": data["evidence"],
        }


def save_results_to_json():
    """Save the crawler results to JSON files."""
    with open("application_links.json", "w") as f:
        json.dump(application_links, f, indent=2)

    # Save a simplified version of forms (without HTML content)
    forms_simplified = []
    for form in forms_found:
        form_copy = form.copy()
        # Truncate the HTML to avoid giant files
        form_copy["form_html"] = (
            form_copy["form_html"][:200] + "..."
            if len(form_copy["form_html"]) > 200
            else form_copy["form_html"]
        )
        forms_simplified.append(form_copy)

    with open("forms_found.json", "w") as f:
        json.dump(forms_simplified, f, indent=2)

    # Save entry points and their classifications
    with open("entry_points.json", "w") as f:
        json.dump(entry_points, f, indent=2)

    logger.info("Results saved to JSON files")


def calculate_confidence_score(entry_point):
    """
    Calculate a confidence score for an entry point based on multiple signals.

    Args:
        entry_point: Dictionary containing entry point data

    Returns:
        A tuple of (score, reasoning) where score is between 0-100
    """
    score = 50  # Start with neutral score
    reasoning = []

    # Boost score based on NLP classification
    if entry_point.get("nlp_classification") == "APPLICATION PORTAL":
        score += 20
        reasoning.append("Classified as application portal by NLP")
    elif entry_point.get("nlp_classification") == "DIRECT APPLICATION":
        score += 15
        reasoning.append("Classified as direct application by NLP")
    elif entry_point.get("nlp_classification") == "INFORMATION PAGE":
        score += 5
        reasoning.append("Classified as information page by NLP")
    elif entry_point.get("nlp_classification") == "UNRELATED":
        score -= 25
        reasoning.append("Classified as unrelated by NLP")

    # Check URL patterns
    url = entry_point.get("url", "").lower()
    if any(pattern in url for pattern in Config.KEYWORDS["url_patterns"]):
        score += 15
        reasoning.append("URL contains application-related patterns")

    # Check for keywords in context
    context = entry_point.get("context", "").lower()
    general_keywords = sum(
        1 for keyword in Config.KEYWORDS["general"] if keyword.lower() in context
    )
    action_keywords = sum(
        1 for keyword in Config.KEYWORDS["action"] if keyword.lower() in context
    )

    if general_keywords > 2:
        score += 10
        reasoning.append(
            f"Context contains {general_keywords} general application keywords"
        )

    if action_keywords > 0:
        score += 15
        reasoning.append(f"Context contains {action_keywords} action-oriented keywords")

    # Check link text or form evidence
    if entry_point["type"] == "link":
        link_text = entry_point.get("link_text", "").lower()
        if any(action in link_text for action in Config.KEYWORDS["action"]):
            score += 10
            reasoning.append("Link text contains action keywords")
    else:  # form type
        evidence = entry_point.get("evidence", [])
        if len(evidence) >= 3:
            score += 10
            reasoning.append(f"Form has {len(evidence)} supporting evidence points")

    # Cap the score between 0 and 100
    score = max(0, min(100, score))

    # Determine review flag based on score
    if score < 40:
        review_flag = "LOW"
    elif score < 70:
        review_flag = "MEDIUM"
    else:
        review_flag = "HIGH"

    return score, review_flag, reasoning


def export_to_json_structured():
    """Export results to a structured JSON file with detailed information and confidence scores."""
    structured_data = []

    for entry_point in entry_points:
        # Calculate confidence score
        confidence_score, review_flag, reasoning = calculate_confidence_score(
            entry_point
        )

        # Create structured record
        record = {
            "university": entry_point.get("university", ""),
            "page_url": entry_point.get("source_url", entry_point.get("url", "")),
            "entry_point_url": entry_point.get("url", ""),
            "type": entry_point.get("type", ""),
            "entry_type": entry_point.get("entry_type", ""),
            "nlp_classification": entry_point.get("nlp_classification", ""),
            "confidence_score": confidence_score,
            "review_flag": review_flag,
            "confidence_reasoning": reasoning,
            "context_snippet": (
                entry_point.get("context", "")[:300]
                if entry_point.get("context")
                else ""
            ),
            "link_text": (
                entry_point.get("link_text", "")
                if entry_point.get("type") == "link"
                else None
            ),
            "evidence": entry_point.get("evidence", []),
            "full_analysis": entry_point.get("full_analysis", ""),
        }

        structured_data.append(record)

    # Get current timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"structured_entry_points_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(structured_data, f, indent=2)

    logger.info(f"Structured JSON report exported to {filename}")

    return filename


def export_to_csv_structured():
    """Export results to a CSV file with key information and confidence scores."""
    # Get current timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"structured_entry_points_{timestamp}.csv"

    # Define CSV fields
    fieldnames = [
        "university",
        "page_url",
        "entry_point_url",
        "type",
        "entry_type",
        "nlp_classification",
        "confidence_score",
        "review_flag",
        "context_snippet",
    ]

    with open(filename, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for entry_point in entry_points:
            # Calculate confidence score
            confidence_score, review_flag, _ = calculate_confidence_score(entry_point)

            # Create record with only the fields needed for CSV
            record = {
                "university": entry_point.get("university", ""),
                "page_url": entry_point.get("source_url", entry_point.get("url", "")),
                "entry_point_url": entry_point.get("url", ""),
                "type": entry_point.get("type", ""),
                "entry_type": entry_point.get("entry_type", ""),
                "nlp_classification": entry_point.get("nlp_classification", ""),
                "confidence_score": confidence_score,
                "review_flag": review_flag,
                "context_snippet": (
                    entry_point.get("context", "")[:100]
                    if entry_point.get("context")
                    else ""
                ),
            }

            writer.writerow(record)

    logger.info(f"CSV report exported to {filename}")

    return filename


def generate_summary_report():
    """Generate a summary report of all findings."""
    # Calculate overall statistics
    total_entry_points = len(entry_points)

    # Count by university
    university_counts = {}
    for entry in entry_points:
        univ = entry.get("university", "Unknown")
        if univ not in university_counts:
            university_counts[univ] = 0
        university_counts[univ] += 1

    # Count by classification
    classification_counts = {}
    for entry in entry_points:
        classification = entry.get("nlp_classification", "Unknown")
        if classification not in classification_counts:
            classification_counts[classification] = 0
        classification_counts[classification] += 1

    # Count by confidence level
    confidence_levels = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for entry in entry_points:
        _, review_flag, _ = calculate_confidence_score(entry)
        confidence_levels[review_flag] += 1

    # Generate the report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"summary_report_{timestamp}.txt"

    with open(filename, "w") as f:
        f.write("=== University Application Entry Points Summary Report ===\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"Total Entry Points Discovered: {total_entry_points}\n\n")

        f.write("--- By University ---\n")
        for univ, count in university_counts.items():
            f.write(f"{univ}: {count} entry points\n")

        f.write("\n--- By Classification ---\n")
        for classification, count in classification_counts.items():
            f.write(f"{classification}: {count} entry points\n")

        f.write("\n--- By Confidence Level ---\n")
        for level, count in confidence_levels.items():
            f.write(f"{level} confidence: {count} entry points\n")

        f.write("\n--- Top HIGH Confidence Entry Points ---\n")
        high_confidence_entries = []
        for entry in entry_points:
            score, flag, _ = calculate_confidence_score(entry)
            if flag == "HIGH":
                high_confidence_entries.append((score, entry))

        # Sort by score descending
        high_confidence_entries.sort(reverse=True)

        # Display top 5 high confidence entries
        for i, (score, entry) in enumerate(high_confidence_entries[:5], 1):
            f.write(f"{i}. {entry.get('university', '')}: {entry.get('url', '')}\n")
            f.write(
                f"   Type: {entry.get('type', '')} - {entry.get('nlp_classification', '')}\n"
            )
            f.write(f"   Confidence Score: {score}\n")
            f.write(f"   {'-' * 40}\n")

    logger.info(f"Summary report exported to {filename}")

    return filename


async def main_async():
    """Asynchronous main function to run the crawler."""
    logger.info("Starting crawler")

    # Seed the queue with the base URLs for each university
    for university in Config.SEED_UNIVERSITIES:
        url_queue.put((university["base_url"], Config.MAX_DEPTH, university))
        logger.info(f"Added seed URL {university['base_url']} for {university['name']}")

    # Create a client session
    async with aiohttp.ClientSession() as session:
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Start multiple worker tasks
        workers = []
        for i in range(Config.NUM_WORKERS):
            worker = asyncio.create_task(crawl_worker(semaphore, session))
            workers.append(worker)
            logger.info(f"Started worker task {i}")

        # Wait for all workers to complete
        await asyncio.gather(*workers)

        # Process URLs that need JavaScript rendering
        if urls_needing_js:
            logger.info(
                f"Found {len(urls_needing_js)} URLs that need JavaScript rendering"
            )

            # Initialize Playwright
            playwright, browser = await setup_playwright()

            # Process each URL with Playwright
            for url in urls_needing_js:
                university_domain = urlparse(url).netloc
                university = next(
                    (
                        u
                        for u in Config.SEED_UNIVERSITIES
                        if u["domain"] in university_domain
                    ),
                    None,
                )

                if university:
                    logger.info(
                        f"Processing {url} with Playwright for {university['name']}"
                    )
                    await process_with_playwright(url, 0, university, browser)

                    # Apply politeness delay
                    await asyncio.sleep(Config.REQUEST_DELAY)

            # Close Playwright
            await close_playwright(playwright, browser)

    # Process and classify entry points
    logger.info("\nClassifying Entry Points...")
    classified_results = []

    for idx, entry_point in enumerate(entry_points, start=1):
        logger.info(
            f"Classifying entry point {idx}/{len(entry_points)}: {entry_point['url']}"
        )
        classification = classify_entry_point(entry_point)
        classified_results.append(classification)
        logger.info(f"Classification: {classification['nlp_classification']}")

    # Add classifications to entry points
    for result in classified_results:
        for entry_point in entry_points:
            if id(entry_point) == result["id"]:
                entry_point["nlp_classification"] = result["nlp_classification"]
                entry_point["full_analysis"] = result["full_analysis"]
                break

    # Save results to JSON files
    save_results_to_json()

    # Export structured data
    json_filename = export_to_json_structured()
    csv_filename = export_to_csv_structured()
    summary_filename = generate_summary_report()

    # Final summary
    logger.info("\nClassification Summary:")

    # Count by classification type
    classification_counts = {}
    for result in classified_results:
        category = result["nlp_classification"]
        if category not in classification_counts:
            classification_counts[category] = 0
        classification_counts[category] += 1

    for category, count in classification_counts.items():
        logger.info(f"{category}: {count} entries")

    logger.info("\nStructured reports generated:")
    logger.info(f"- JSON Report: {json_filename}")
    logger.info(f"- CSV Report: {csv_filename}")
    logger.info(f"- Summary Report: {summary_filename}")

    logger.info("\nCrawler completed successfully")


def main():
    """Main function to run the crawler."""
    # Run the async main function
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
