#!/usr/bin/env python3
"""
University Application Crawler - Main Application Entry Point

This script runs the crawler to find university application pages.
"""
import asyncio
import argparse
import os
import sys
import signal
import time
from datetime import datetime
import uuid

import aiohttp
from loguru import logger

from config import Config
from utils.logging_config import configure_logging
from crawler.queue import UniqueURLQueue
from crawler.worker import start_workers
from crawler.monitor import monitor_progress, explore_specific_application_paths
from crawler.shutdown import check_for_shutdown, setup_signal_handlers
from analysis.ai_evaluator import evaluate_all_applications, get_api_metrics
from output.exporter import save_results
from output.report_generator import ReportGenerator
from database.db_operations import init_database, start_crawl_run, end_crawl_run
from database.metrics_storage import (
    save_metrics_to_db,
    save_application_pages,
    get_aggregated_metrics,
)
from models.crawl_stats import CrawlStats, APIMetrics
from models.state_manager import state_manager  # Use the global instance


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="University Application Crawler")

    # Basic configuration
    parser.add_argument(
        "-u",
        "--university",
        nargs="+",
        help="Specify universities to crawl (e.g., Stanford MIT)",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=Config.MAX_DEPTH,
        help=f"Maximum crawl depth (default: {Config.MAX_DEPTH})",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=Config.NUM_WORKERS,
        help=f"Number of worker tasks (default: {Config.NUM_WORKERS})",
    )
    parser.add_argument(
        "-m",
        "--max-urls",
        type=int,
        default=Config.MAX_TOTAL_URLS,
        help=f"Maximum URLs to crawl (default: {Config.MAX_TOTAL_URLS})",
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output-dir",
        default="outputs",
        help="Directory to save outputs (default: outputs)",
    )
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML report with visualizations",
    )
    parser.add_argument("--csv", action="store_true", help="Export results to CSV")

    # Database options
    parser.add_argument(
        "--use-db",
        action="store_true",
        default=Config.USE_SQLITE,
        help="Use SQLite database for storing results and metrics",
    )

    # Model options
    parser.add_argument(
        "--model",
        default=Config.MODEL_NAME,
        help=f"OpenAI model to use (default: {Config.MODEL_NAME})",
    )
    parser.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="Skip AI evaluation of found pages",
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file", default="crawler.log", help="Log file path (default: crawler.log)"
    )

    return parser.parse_args()


def update_config_from_args(args):
    """Update configuration based on command line arguments."""
    Config.MAX_DEPTH = args.depth
    Config.NUM_WORKERS = args.workers
    Config.MAX_TOTAL_URLS = args.max_urls
    Config.MODEL_NAME = args.model
    Config.USE_SQLITE = args.use_db

    # Update universities if specified
    if args.university:
        # Filter existing universities or add them
        selected_universities = []
        university_names = [u.lower() for u in args.university]

        # First check existing ones
        for uni in Config.SEED_UNIVERSITIES:
            if uni["name"].lower() in university_names:
                selected_universities.append(uni)

        # Only use selected ones if any were found
        if selected_universities:
            Config.SEED_UNIVERSITIES = selected_universities
        else:
            logger.warning("No matching universities found in configuration")


async def prepare_url_queue(url_queue):
    """Prepare the URL queue with seed URLs."""
    for university in Config.SEED_UNIVERSITIES:
        # Add the main university domain
        # Use priority 0 for seed URLs
        await url_queue.put((0, university["base_url"], Config.MAX_DEPTH, university))

        # Add known admission subdomains as seeds
        university_domain = university["domain"]
        if university_domain in Config.ADMISSION_SUBDOMAINS:
            for subdomain in Config.ADMISSION_SUBDOMAINS[university_domain]:
                admission_url = f"https://{subdomain}/"
                logger.info(f"Adding admission seed URL: {admission_url}")
                # Use priority 0 for seed URLs
                await url_queue.put((0, admission_url, Config.MAX_DEPTH, university))

                # Add common application paths to these admission domains
                for path in [
                    "/apply",
                    "/first-year",
                    "/apply/first-year",
                    "/undergraduate",
                    "/apply/undergraduate",
                    "/freshman",
                    "/admission",
                    "/admissions",
                ]:
                    path_url = f"https://{subdomain}{path}"
                    logger.info(f"Adding admission path URL: {path_url}")
                    # Use priority 0 for seed URLs
                    await url_queue.put((0, path_url, Config.MAX_DEPTH, university))


async def main():
    """Main application function."""
    # Parse arguments
    args = parse_arguments()

    # Configure logging
    configure_logging(log_file=args.log_file, log_level=args.log_level)

    # Update configuration
    update_config_from_args(args)

    # Generate a unique run ID
    run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # Initialize stats
    crawl_stats = CrawlStats()

    # Initialize URL queue
    url_queue = UniqueURLQueue()

    # Set up signal handlers
    setup_signal_handlers()

    # Initialize database if enabled
    if Config.USE_SQLITE:
        try:
            await init_database()
            logger.info("Database initialized successfully")

            # Record crawl start
            university_name = (
                Config.SEED_UNIVERSITIES[0]["name"]
                if Config.SEED_UNIVERSITIES
                else "Unknown"
            )
            await start_crawl_run(run_id, university_name)

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            Config.USE_SQLITE = False

    logger.info(f"Starting crawler run {run_id}")
    logger.info(
        f"Targeting universities: {', '.join(u['name'] for u in Config.SEED_UNIVERSITIES)}"
    )

    # Initialize URL queue with seed URLs
    await prepare_url_queue(url_queue)

    try:
        # Start crawler
        async with aiohttp.ClientSession() as session:
            # Start monitor task
            monitor_task = asyncio.create_task(monitor_progress(url_queue))

            # Start workers
            workers = await start_workers(session, url_queue, Config.NUM_WORKERS)

            try:
                # Wait for queue to be empty or max URLs to be reached
                while await state_manager.is_crawler_running():
                    if await check_for_shutdown():
                        state_manager.stop_crawler()
                        break

                    if url_queue.empty():
                        logger.info("Queue is empty, crawling complete")
                        break

                    # Check URL limit
                    counters = await state_manager.get_counters()
                    if counters["visited"] >= Config.MAX_TOTAL_URLS:
                        logger.info(
                            f"Reached maximum total URLs limit ({Config.MAX_TOTAL_URLS})"
                        )
                        await state_manager.stop_crawler()
                        break

                    await asyncio.sleep(1)

                logger.info("Crawler reached completion criteria")

                # Give workers time to finish current tasks
                try:
                    await asyncio.wait_for(url_queue.join(), timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for queue to empty")

            except asyncio.CancelledError:
                logger.info("Crawler task cancelled")
            except Exception as e:
                logger.error(f"Error in main crawl loop: {e}")
            finally:
                # Request workers to stop
                await state_manager.stop_crawler()

                # Cancel workers and monitor
                for w in workers:
                    w.cancel()

                monitor_task.cancel()

                # Wait for cancellation to complete
                await asyncio.gather(*workers, monitor_task, return_exceptions=True)

            # Explore specific application paths if admission domains were found
            admission_domains = await state_manager.get_admission_domains()
            if admission_domains:
                logger.info(
                    "Exploring specific application paths on admission domains..."
                )
                await explore_specific_application_paths()

            # Evaluate application pages with AI
            evaluated_results = []
            found_applications = await state_manager.get_application_pages()

            if found_applications:
                logger.info(
                    f"Found {len(found_applications)} potential application pages"
                )

                if not args.skip_evaluation:
                    try:
                        evaluated_results = await evaluate_all_applications(
                            found_applications
                        )

                        if evaluated_results:
                            actual_count = sum(
                                1
                                for app in evaluated_results
                                if app.get("is_actual_application", False)
                            )
                            logger.success(
                                f"Identified {actual_count} actual application pages out of {len(evaluated_results)} candidates"
                            )

                            # Save to database if enabled
                            if Config.USE_SQLITE:
                                await save_application_pages(evaluated_results, run_id)

                                # Save API metrics
                                api_metrics = get_api_metrics()
                                await save_metrics_to_db(api_metrics, run_id)
                    except Exception as e:
                        logger.error(f"Error during evaluation: {e}")
                else:
                    logger.info("Skipping AI evaluation as requested")
                    evaluated_results = found_applications
            else:
                logger.warning("No application pages found")

            # Save results
            try:
                os.makedirs(args.output_dir, exist_ok=True)
                original_file, evaluated_file, summary_file = save_results(
                    found_applications,
                    evaluated_results if evaluated_results else None,
                    get_api_metrics() if not args.skip_evaluation else None,
                    output_dir=args.output_dir,
                )

                logger.success(f"Results saved to {args.output_dir}")

                # Generate HTML report if requested
                if args.html_report and evaluated_results:
                    report_generator = ReportGenerator(
                        output_dir=os.path.join(args.output_dir, "reports")
                    )
                    report_file = await report_generator.generate_full_report(
                        evaluated_results,
                        crawl_stats.__dict__,
                        get_api_metrics() if not args.skip_evaluation else None,
                    )
                    logger.success(f"HTML report generated: {report_file}")

                # Export to CSV if requested
                if args.csv and evaluated_results:
                    from output.exporter import export_to_csv

                    csv_file = os.path.join(
                        args.output_dir,
                        f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    )
                    export_to_csv(evaluated_results, csv_file)

            except Exception as e:
                logger.error(f"Error saving results: {e}")

            # Update database with final stats if enabled
            if Config.USE_SQLITE:
                try:
                    counters = await state_manager.get_counters()
                    await end_crawl_run(
                        run_id,
                        counters["visited"],
                        len(found_applications),
                        (
                            len(
                                [
                                    a
                                    for a in evaluated_results
                                    if a.get("is_actual_application", False)
                                ]
                            )
                            if evaluated_results
                            else 0
                        ),
                    )
                except Exception as e:
                    logger.error(f"Error updating database with final stats: {e}")

    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
    finally:
        logger.success(f"Crawler run {run_id} completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unhandled exception: {e}")
        sys.exit(1)
