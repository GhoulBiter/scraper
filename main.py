import threading
import queue
import time
import os
import json
import logging
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


# Configuration module instead of hard-coded values
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

    # Keywords for application pages (will be expanded in iteration 2)
    KEYWORDS = [
        "bachelor",
        "undergraduate",
        "apply",
        "application",
        "admission",
        "major",
        "enroll",
        "register",
    ]


# Shared data structures and locks
url_queue = queue.Queue()
visited = {}  # Changed to dict: {domain: set(urls)} to manage per-university
visited_lock = threading.Lock()

application_links = (
    {}
)  # Mapping: {normalized_link: {"page_url": url, "university": name}}
application_links_lock = threading.Lock()

forms_found = []  # List of dicts with form info
forms_found_lock = threading.Lock()


def normalize_url(url):
    """Normalize a URL by removing its fragment (the part after #)."""
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="").geturl()
    return normalized


def get_domain(url):
    """Extract the domain from a URL."""
    return urlparse(url).netloc


def get_driver():
    """Initialize and return a headless Chrome webdriver instance."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)


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

    # Check if we've already visited this URL (ignoring fragments)
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

            with forms_found_lock:
                forms_found.append(
                    {
                        "form_url": full_form_url,
                        "page_url": normalized_current_url,
                        "university": university["name"],
                        "form_html": form_html,
                    }
                )
            logger.info(
                f"Found form: {full_form_url} on page: {normalized_current_url}"
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
                anchor_data.append((href, text))
        except StaleElementReferenceException:
            continue

    for href, text in anchor_data:
        try:
            full_url = href if href.startswith("http") else urljoin(current_url, href)
            normalized_full_url = normalize_url(full_url)
            parsed_url = urlparse(normalized_full_url)

            # Check if the URL belongs to the university domain
            if university_domain not in parsed_url.netloc:
                continue

            # Check for keywords to identify potential application links
            if any(
                keyword in text.lower() or keyword in normalized_full_url.lower()
                for keyword in Config.KEYWORDS
            ):
                with application_links_lock:
                    if normalized_full_url not in application_links:
                        application_links[normalized_full_url] = {
                            "page_url": normalized_current_url,
                            "university": university["name"],
                        }
                        logger.info(
                            f"Found potential application link: {normalized_full_url} on page: {normalized_current_url}"
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


def classify_form(form_html, page_url, university_name):
    """
    Uses the OpenAI API to determine if a given HTML form (with its page context)
    appears to be an application form for university bachelor's programs.

    Args:
        form_html: HTML content of the form
        page_url: URL of the page containing the form
        university_name: Name of the university being processed
    """
    prompt = (
        f"Given the following HTML form and the page URL where it was found, "
        f"determine if this form appears to be an application form for {university_name}'s bachelor's programs "
        f"or a portal to access such applications. "
        f"Answer with a clear 'Yes' or 'No' and provide a brief explanation.\n\n"
        f"Page URL: {page_url}\n\nForm HTML:\n{form_html}"
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that analyzes HTML forms to determine if they are application forms or portals for university bachelor's programs.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        classification = response.choices[0].message.content
        return classification
    except Exception as e:
        logger.error(f"Error during classification for form on {page_url}: {e}")
        return "Classification error."


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

    logger.info("Results saved to JSON files")


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

    logger.info("\nForms Found:")
    for form in forms_found:
        logger.info(
            f"Form URL: {form['form_url']}, Found on: {form['page_url']} for {form['university']}"
        )

    # Process and classify forms
    logger.info("\nForm Classification Results:")
    for idx, form in enumerate(forms_found, start=1):
        logger.info(f"\nForm {idx}:")
        logger.info(f"Form URL: {form['form_url']}")
        logger.info(f"Found on Page: {form['page_url']}")
        logger.info(f"University: {form['university']}")
        classification = classify_form(
            form["form_html"], form["page_url"], form["university"]
        )
        logger.info(f"Classification: {classification}")

    # Save results to JSON files
    save_results_to_json()

    logger.info("Crawler completed successfully")


if __name__ == "__main__":
    main()
