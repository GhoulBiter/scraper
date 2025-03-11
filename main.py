import time
import os
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Base settings
BASE_URL = "https://www.mit.edu"
DOMAIN = "mit.edu"
MAX_DEPTH = 2  # Adjust this value to control the depth of crawling

visited = set()
application_links = {}  # Mapping: {found_link: page_url}
forms_found = (
    []
)  # List of dictionaries: {"form_url": ..., "page_url": ..., "form_html": ...}


def crawl(driver, url, depth):
    if depth <= 0:
        return
    try:
        print(f"Crawling: {url}")
        driver.get(url)
        # Wait for dynamic content to load; adjust sleep time if necessary
        time.sleep(2)
    except Exception as e:
        print(f"Error loading {url}: {e}")
        return

    current_url = driver.current_url

    # Extract all forms on the page
    forms = driver.find_elements(By.TAG_NAME, "form")
    for form in forms:
        try:
            form_action = form.get_attribute("action")
            if not form_action:
                continue
            # Resolve relative URLs
            full_form_url = (
                form_action
                if form_action.startswith("http")
                else urljoin(current_url, form_action)
            )
            form_html = form.get_attribute("outerHTML")
            # Store the form details along with the page where it was found
            forms_found.append(
                {
                    "form_url": full_form_url,
                    "page_url": current_url,
                    "form_html": form_html,
                }
            )
            print(f"Found form: {full_form_url} on page: {current_url}")
        except Exception as e:
            print(f"Error processing a form on {current_url}: {e}")
            continue

    # Extract all anchor tags and look for potential application links
    anchors = driver.find_elements(By.TAG_NAME, "a")
    for a in anchors:
        try:
            href = a.get_attribute("href")
            if not href:
                continue
            # Handle relative URLs
            full_url = href if href.startswith("http") else urljoin(current_url, href)
            parsed_url = urlparse(full_url)
            # Process only links within the MIT domain
            if DOMAIN not in parsed_url.netloc:
                continue

            # Define keywords that may indicate a link to an application or admissions page
            keywords = [
                "bachelor",
                "undergraduate",
                "apply",
                "application",
                "admission",
                "major",
            ]
            link_text = a.text.lower() if a.text else ""
            url_lower = full_url.lower()

            if any(
                keyword in link_text or keyword in url_lower for keyword in keywords
            ):
                if full_url not in application_links:
                    application_links[full_url] = current_url
                    print(
                        f"Found potential application link: {full_url} on page: {current_url}"
                    )

            # Continue crawling new URLs that have not been visited
            if full_url not in visited:
                visited.add(full_url)
                crawl(driver, full_url, depth - 1)
        except Exception as e:
            print(f"Error processing a link on {current_url}: {e}")
            continue


def classify_form(form_html, page_url):
    """
    Uses the OpenAI API to determine if a given form (with its HTML content and page context)
    is likely the application form for MIT's bachelor's majors.
    """
    prompt = (
        f"Given the following HTML form and the page URL where it was found, "
        f"determine if this form appears to be the application form for MIT's bachelor's majors. "
        f"Answer with a clear 'Yes' or 'No' and provide a brief explanation.\n\n"
        f"Page URL: {page_url}\n\nForm HTML:\n{form_html}"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that analyzes HTML forms to determine if they are application forms for MIT bachelor's majors.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        classification = response["choices"][0]["message"]["content"]
        return classification
    except Exception as e:
        print(f"Error during classification for form on {page_url}: {e}")
        return "Classification error."


if __name__ == "__main__":
    # Set up Selenium Chrome options for headless browsing
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=options)
    try:
        visited.add(BASE_URL)
        crawl(driver, BASE_URL, MAX_DEPTH)
    finally:
        driver.quit()

    # Print out candidate application links
    print("\nCandidate Application Links (found on corresponding pages):")
    for link, page in application_links.items():
        print(f"Link: {link}\nFound on: {page}\n")

    # Use OpenAI API to classify each found form
    print("\nForm Classification Results:")
    for idx, form in enumerate(forms_found, start=1):
        print(f"\nForm {idx}:")
        print(f"Form URL: {form['form_url']}")
        print(f"Found on Page: {form['page_url']}")
        classification = classify_form(form["form_html"], form["page_url"])
        print(f"Classification: {classification}")

    # If you prefer to use a local model with ollama, replace the 'classify_form' function's call
    # to openai.ChatCompletion.create with the appropriate API call to your local model.
