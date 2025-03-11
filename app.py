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


def get_driver():
    """Initialize and return a headless Chrome webdriver instance."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)


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


def crawl_url(driver, url, depth, university):
    """
    Crawl a single URL, extract forms and links, and add new URLs to the queue.

    Args:
        driver: The Selenium webdriver instance
        url: The URL to crawl
        depth: Current crawl depth
        university: Dictionary containing university information
    """
    if depth <= 0:
        return

    normalized_url = normalize_url(url)
    university_domain = university["domain"]

    # Check if we've already visited this URL
    with visited_lock:
        if university_domain not in visited:
            visited[university_domain] = set()
        if normalized_url in visited[university_domain]:
            return
        visited[university_domain].add(normalized_url)

    # Add politeness delay
    time.sleep(Config.REQUEST_DELAY)

    try:
        driver.set_page_load_timeout(10)
        driver.get(url)
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "a"))
        )
    except Exception as e:
        logger.error(f"Error loading {url}: {e}")
        return

    current_url = driver.current_url
    normalized_current_url = normalize_url(current_url)
    page_source = driver.page_source
    page_title = driver.title

    # Process forms on the page
    try:
        forms = driver.find_elements(By.TAG_NAME, "form")
        logger.info(f"Found {len(forms)} forms on {normalized_current_url}")
    except Exception as e:
        logger.error(f"Error finding forms on {normalized_current_url}: {e}")
        forms = []

    for form in forms:
        try:
            form_action = form.get_attribute("action")
            if not form_action:
                continue

            full_form_url = (
                form_action
                if form_action.startswith("http")
                else urljoin(current_url, form_action)
            )
            form_html = form.get_attribute("outerHTML")
            form_context = extract_context(form, page_source)

            # Analyze the form to determine if it's a portal or direct application
            form_type, evidence = analyze_form_type(form)

            form_data = {
                "form_url": full_form_url,
                "page_url": normalized_current_url,
                "page_title": page_title,
                "university": university["name"],
                "form_html": form_html,
                "context": form_context,
                "form_type": form_type,
                "evidence": evidence,
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
                        }
                    )

            logger.info(
                f"Found form: {full_form_url} on page: {normalized_current_url} (Type: {form_type})"
            )
        except Exception as e:
            logger.error(f"Error processing form on {normalized_current_url}: {e}")
            continue

    # Extract and process anchor tags
    try:
        anchors = driver.find_elements(By.TAG_NAME, "a")
        logger.info(f"Found {len(anchors)} anchors on {normalized_current_url}")
    except Exception as e:
        logger.error(f"Error finding anchors on {normalized_current_url}: {e}")
        anchors = []

    # Extract href and text from anchors (to avoid stale element issues)
    anchor_data = []
    for a in anchors:
        try:
            href = a.get_attribute("href")
            text = a.text
            if href:
                anchor_data.append((href, text, a))
        except StaleElementReferenceException:
            continue

    for href, text, a_element in anchor_data:
        try:
            if not href:
                continue

            full_url = href if href.startswith("http") else urljoin(current_url, href)
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
                context = extract_context(a_element, page_source)

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
                                }
                            )

                        logger.info(
                            f"Found potential application link: {normalized_full_url} on page: {normalized_current_url}"
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
            continue


def worker():
    """Worker function to process URLs from the queue."""
    driver = get_driver()
    while True:
        try:
            url, depth, university = url_queue.get(timeout=10)
            logger.info(f"Processing {url} at depth {depth} for {university['name']}")
            crawl_url(driver, url, depth, university)
            url_queue.task_done()
        except queue.Empty:
            logger.info("Queue is empty, worker thread finishing")
            break
        except Exception as e:
            logger.error(f"Unexpected error in worker thread: {e}")
            url_queue.task_done()  # Make sure to mark task as done even on error
    driver.quit()


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


def main():
    """Main function to run the crawler."""
    logger.info("Starting crawler")

    # Seed the queue with the base URLs for each university
    for university in Config.SEED_UNIVERSITIES:
        url_queue.put((university["base_url"], Config.MAX_DEPTH, university))
        logger.info(f"Added seed URL {university['base_url']} for {university['name']}")

    # Start worker threads
    threads = []
    for i in range(Config.NUM_WORKERS):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
        logger.info(f"Started worker thread {i}")

    # Wait for all URLs to be processed
    url_queue.join()
    for t in threads:
        t.join()

    logger.info("All worker threads completed")

    # Print summary results
    logger.info("\nCandidate Application Links:")
    for link, data in application_links.items():
        logger.info(
            f"Link: {link} found on {data['page_url']} for {data['university']}"
        )
        logger.info(f"Match reason: {', '.join(data['match_reason'])}")
        logger.info(f"Entry type: {data['entry_type']}")
        if "portal_evidence" in data and data["portal_evidence"]:
            logger.info(f"Portal evidence: {', '.join(data['portal_evidence'])}")

    logger.info("\nForms Found:")
    for form in forms_found:
        logger.info(
            f"Form URL: {form['form_url']}, Found on: {form['page_url']} for {form['university']}"
        )
        logger.info(
            f"Form type: {form['form_type']}, Evidence: {', '.join(form['evidence'])}"
        )

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


if __name__ == "__main__":
    main()
