"""
Progress monitoring for the crawler
"""

import asyncio
import time
import aiohttp
import re
from loguru import logger

from config import Config
from analysis.page_analyzer import extract_title, is_application_page
from models.state_manager import state_manager


async def monitor_progress(url_queue):
    """Monitor and report crawler progress."""
    last_time = time.time()
    last_visited = 0

    while await state_manager.is_crawler_running():
        try:
            await asyncio.sleep(5)

            # Get current counters
            counters = await state_manager.get_counters()
            current_time = time.time()
            elapsed = current_time - last_time
            visited_delta = counters["visited"] - last_visited
            rate = visited_delta / elapsed if elapsed > 0 else 0

            # Get application pages count
            application_pages = await state_manager.get_application_pages()

            logger.info(
                f"Progress: {counters['visited']} URLs visited, {url_queue.qsize()} queued, "
                f"{len(application_pages)} application pages found, {rate:.1f} URLs/sec"
            )

            # Log admission domains we've found
            admission_domains = await state_manager.get_admission_domains()
            if admission_domains:
                logger.info(f"Found admission domains: {', '.join(admission_domains)}")

            # Log domains with highest counts
            top_domains = await state_manager.get_top_domains(5)
            if top_domains:
                logger.info(
                    f"Top domains: {', '.join([f'{d}({c})' for d, c in top_domains])}"
                )

            # Check if queue is empty or URL limit reached
            if (url_queue.empty() and counters["visited"] > 0) or counters[
                "queued"
            ] >= Config.MAX_TOTAL_URLS:
                logger.info("Queue is empty or URL limit reached, crawling complete")
                await state_manager.stop_crawler()
                break

            last_time = current_time
            last_visited = counters["visited"]

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")


async def explore_specific_application_paths():
    """Directly check common application paths on found admission domains."""
    admission_domains = await state_manager.get_admission_domains()
    if not admission_domains:
        return

    logger.info(
        f"Exploring specific application paths on {len(admission_domains)} admission domains"
    )

    async with aiohttp.ClientSession() as session:
        for domain in admission_domains:
            # Common application paths to check directly
            specific_paths = [
                "/apply",
                "/apply/",  # With trailing slash
                "/apply/first-year",
                "/apply/first-year/",  # With trailing slash
                "/apply/freshman",
                "/apply/undergraduate",
                "/application",
                "/admission/apply",
                "/admission/first-year",
                "/admission/freshman",
            ]

            for path in specific_paths:
                full_url = f"https://{domain}{path}"
                if await state_manager.is_url_visited(full_url):
                    continue

                await check_direct_application_path(full_url, domain, session, path)


async def check_direct_application_path(full_url, domain, session, current_path=None):
    """Check a specific URL for application content."""
    logger.info(f"Directly checking potential application path: {full_url}")
    try:
        # Use a default timeout if REQUEST_TIMEOUT is not defined in Config
        timeout_value = getattr(Config, "REQUEST_TIMEOUT", 15)  # Default 15 seconds

        async with session.get(full_url, timeout=timeout_value) as response:
            if response.status == 200:
                html = await response.text()
                title = extract_title(html)

                # Skip 404 pages even if they return 200 status
                if "not found" in title.lower():
                    logger.warning(f"Skipping 404 page: {full_url} - {title}")
                    return

                # Check if this is an application page
                is_app_page, reasons = is_application_page(full_url, html, title)
                if is_app_page:
                    logger.success(
                        f"Found direct application path: {full_url} - {title}"
                    )
                    # Add to found applications through state manager
                    for university in Config.SEED_UNIVERSITIES:
                        if university["domain"] in domain:
                            await state_manager.add_application_page(
                                {
                                    "url": full_url,
                                    "title": title,
                                    "university": university["name"],
                                    "reasons": reasons,
                                    "depth": 0,
                                    "html_snippet": html[:5000],
                                }
                            )
                            break

                # If we find a valid /apply path, recursively check its subpaths
                if (
                    current_path
                    and ("/apply" in current_path or current_path.endswith("/apply/"))
                    and "not found" not in title.lower()
                ):
                    university_name = next(
                        (
                            u["name"]
                            for u in Config.SEED_UNIVERSITIES
                            if u["domain"] in domain
                        ),
                        "Unknown University",
                    )
                    await check_subpaths(full_url, university_name, session)

    except Exception as e:
        logger.error(f"Error checking direct path {full_url}: {e}")


async def check_subpaths(base_url, university_name, session):
    """Recursively check subpaths of a valid application URL."""
    logger.info(f"Checking subpaths of {base_url}")

    # Define application subpaths to check
    subpaths = [
        "first-year",
        "first-year/",
        "freshman",
        "freshman/",
        "undergraduate",
        "undergraduate/",
        "transfer",
        "transfer/",
    ]

    for subpath in subpaths:
        if base_url.endswith("/"):
            full_url = f"{base_url}{subpath}"
        else:
            full_url = f"{base_url}/{subpath}"

        if await state_manager.is_url_visited(full_url):
            continue

        # Mark as visited
        await state_manager.add_visited_url(full_url)

        logger.info(f"Checking application subpath: {full_url}")
        try:
            # Use default timeout if Config.REQUEST_TIMEOUT is not available
            timeout_value = getattr(Config, "REQUEST_TIMEOUT", 15)

            async with session.get(full_url, timeout=timeout_value) as response:
                if response.status == 200:
                    html = await response.text()
                    title = extract_title(html)

                    # Skip 404 pages
                    if "not found" in title.lower() or "page not found" in html.lower():
                        logger.warning(f"Skipping 404 page: {full_url} - {title}")
                        continue

                    # Check if this is an application page
                    is_app_page, reasons = is_application_page(full_url, html, title)
                    if is_app_page:
                        logger.success(
                            f"Found application subpath: {full_url} - {title}"
                        )
                        # Add to found applications using state manager
                        await state_manager.add_application_page(
                            {
                                "url": full_url,
                                "title": title,
                                "university": university_name,
                                "reasons": reasons,
                                "depth": 0,
                                "html_snippet": html[:5000],
                            }
                        )

                    # Also check for specific keywords in the HTML that might indicate application content
                    if any(
                        term in html.lower()
                        for term in [
                            "application form",
                            "common app",
                            "apply now",
                            "application deadline",
                        ]
                    ):
                        logger.success(
                            f"Found application-related content: {full_url} - {title}"
                        )
                        # Add to found applications if not already added
                        if not is_app_page:
                            await state_manager.add_application_page(
                                {
                                    "url": full_url,
                                    "title": title,
                                    "university": university_name,
                                    "reasons": ["Contains application-related content"],
                                    "depth": 0,
                                    "html_snippet": html[:5000],
                                }
                            )
        except Exception as e:
            logger.error(f"Error checking subpath {full_url}: {e}")
