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
import atexit
from datetime import datetime
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

import aiohttp
from loguru import logger

from config import Config
from output.how_to_apply_report import (
    export_how_to_apply_csv,
    generate_how_to_apply_report,
)
from utils.logging_config import configure_logging
from crawler.queue import UniqueURLQueue
from crawler.worker import start_workers
from crawler.monitor import monitor_progress, explore_specific_application_paths
from crawler.shutdown import (
    check_for_shutdown,
    setup_signal_handlers,
    shutdown_controller,
)
from analysis.ai_evaluator import evaluate_all_applications, get_api_metrics
from output.exporter import export_to_csv, save_results
from database.db_operations import (
    init_database,
    start_crawl_run,
    end_crawl_run,
    close_connection,
)
from database.metrics_storage import (
    save_metrics_to_db,
    save_application_pages,
    get_aggregated_metrics,
)
from models.crawl_stats import CrawlStats, APIMetrics
from models.state_manager import state_manager  # Use the global instance
from models.checkpoint_manager import CheckpointManager  # New import for checkpointing

# Global shutdown flag for force exit
_force_exit_event = threading.Event()

# Global thread pool executor for API calls
api_executor = ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_API_CALLS)

# Before declaring queue empty, wait to see if more URLs are discovered
consecutive_empty_checks = 0
EMPTY_THRESHOLD = 3  # Require multiple consecutive empty checks


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

    # Checkpoint options
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=60,  # Default: check every 60 seconds
        help="Time between checkpoint evaluations in seconds (default: 60)",
    )
    parser.add_argument(
        "--min-batch-size",
        type=int,
        default=10,  # Default: minimum 10 pages to process
        help="Minimum number of pages to trigger a checkpoint (default: 10)",
    )
    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=30,  # Default: maximum 30 pages per batch
        help="Maximum number of pages to process in one batch (default: 30)",
    )
    parser.add_argument(
        "--disable-checkpoints",
        action="store_true",
        help="Disable incremental checkpoints (process all at once)",
    )

    # Shutdown options
    parser.add_argument(
        "--shutdown-timeout",
        type=int,
        default=30,  # Default: 30 seconds before force exit
        help="Timeout in seconds before forcing program termination on shutdown (default: 30)",
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
    """Prepare the URL queue with seed URLs for each university and its admissions subdomains."""
    # Use the common admission paths list from the Config
    for university in Config.SEED_UNIVERSITIES:
        # Enqueue the main university URL as a seed (priority 0)
        main_url = university.get("base_url")
        if main_url:
            await url_queue.put((0, main_url, Config.MAX_DEPTH, university))
            logger.info(f"Added main seed URL: {main_url}")

        # Add known admission subdomains if available for the university's domain
        university_domain = university.get("domain")
        admission_subdomains = Config.ADMISSION_SUBDOMAINS.get(university_domain, [])
        for subdomain in admission_subdomains:
            # Construct the base admission URL
            admission_url = f"https://{subdomain}/"
            await url_queue.put((0, admission_url, Config.MAX_DEPTH, university))
            logger.info(f"Added admission seed URL: {admission_url}")

            # Enqueue common application paths for this admission subdomain
            for path in Config.VERY_HIGH_PRIORITY_PATTERNS:
                path_url = f"https://{subdomain}{path}"
                await url_queue.put((0, path_url, Config.MAX_DEPTH, university))
                logger.info(f"Added admission path URL: {path_url}")


# Function to force exit after timeout
def force_exit():
    """Force program termination after timeout."""
    if _force_exit_event.is_set():
        logger.critical("Force exit timeout reached. Terminating immediately.")
        os._exit(1)  # Force exit with error code


# Improved signal handler that sets a timer for force exit
def enhanced_signal_handler(signum, frame, timeout=30):
    """Signal handler with force exit capability."""
    logger.warning(
        f"\nReceived exit signal. Will force exit in {timeout} seconds if graceful shutdown fails."
    )

    # Set the force exit event
    _force_exit_event.set()

    # Start a timer for force exit
    timer = threading.Timer(timeout, force_exit)
    timer.daemon = True
    timer.start()

    # Also trigger the regular shutdown process
    asyncio.create_task(shutdown_controller.request_shutdown())


async def shutdown_resources():
    """Clean up resources during shutdown."""
    try:
        # Close database connection if it was used
        if Config.USE_SQLITE:
            await close_connection()
            logger.info("Database connection closed")

        # Shutdown thread pool executor
        api_executor.shutdown(wait=False)
        logger.info("Thread pool executor shutdown initiated")

    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")


async def main():
    """Main application function."""
    global consecutive_empty_checks

    # Parse arguments
    args = parse_arguments()

    # Configure signal handlers with timeout for force exit
    signal.signal(
        signal.SIGINT,
        lambda signum, frame: enhanced_signal_handler(
            signum, frame, args.shutdown_timeout
        ),
    )
    signal.signal(
        signal.SIGTERM,
        lambda signum, frame: enhanced_signal_handler(
            signum, frame, args.shutdown_timeout
        ),
    )

    # Create a synchronous cleanup function for atexit
    def shutdown_resources_sync():
        """Synchronous resource cleanup for atexit."""
        try:
            # Shutdown thread pool executor
            api_executor.shutdown(wait=False)
            logger.info("Thread pool executor shutdown completed")

            # Note: We can't close the database connection here because it's async
            # Database connections will be closed in the main function's finally block

        except Exception as e:
            logger.error(f"Error during sync resource cleanup: {e}")

    # Register the synchronous cleanup function with atexit
    atexit.register(shutdown_resources_sync)

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

    # Initialize checkpoint manager if checkpoints are enabled
    checkpoint_manager = None
    if not args.disable_checkpoints:
        checkpoint_manager = CheckpointManager(
            run_id=run_id,
            output_dir=args.output_dir,
            checkpoint_interval=args.checkpoint_interval,
            min_batch_size=args.min_batch_size,
            max_batch_size=args.max_batch_size,
        )
        # Make checkpoint manager accessible via state manager for monitoring
        state_manager.checkpoint_manager = checkpoint_manager
        logger.info(
            f"Checkpointing enabled: interval={args.checkpoint_interval}s, batch size={args.min_batch_size}-{args.max_batch_size}"
        )
    else:
        logger.info("Checkpointing disabled - will process all pages at the end")

    # Setup for checkpoint processing
    async def process_checkpoint_batch():
        """Process a batch of pending application pages."""
        if not checkpoint_manager:
            return

        # Get a batch for processing
        batch = await checkpoint_manager.get_batch_for_processing()

        if not batch:
            logger.debug("No application pages to process in this batch")
            return

        logger.info(f"Processing checkpoint batch of {len(batch)} application pages")

        # Only evaluate if not skipping evaluation
        if not args.skip_evaluation:
            try:
                # Evaluate the batch
                evaluated_batch = await evaluate_all_applications(batch)

                # Store results
                await checkpoint_manager.add_evaluated_applications(evaluated_batch)

                # Save to database if enabled
                if Config.USE_SQLITE:
                    await save_application_pages(evaluated_batch, run_id)

                actual_count = sum(
                    1
                    for app in evaluated_batch
                    if app.get("is_actual_application", False)
                )
                logger.success(
                    f"Checkpoint: Identified {actual_count} actual application pages out of {len(evaluated_batch)} candidates"
                )

                # Save crawler state
                await checkpoint_manager.save_crawler_state(state_manager)

            except Exception as e:
                logger.error(f"Error processing checkpoint batch: {e}")
        else:
            # If skipping evaluation, just store the batch
            await checkpoint_manager.add_evaluated_applications(batch)
            logger.info(
                f"Checkpoint: Stored {len(batch)} unevaluated application pages (evaluation skipped)"
            )

    # Override add_application_page to use checkpointing
    if checkpoint_manager:
        original_add_application_page = state_manager.add_application_page

        async def add_application_page_with_checkpoint(page):
            """
            Wrapper for state_manager.add_application_page that also adds to checkpoint manager.
            """
            # Call the original method
            await original_add_application_page(page)

            # Add to checkpoint manager
            should_process = await checkpoint_manager.add_application_page(page)

            # If we should process a batch, do it now
            if should_process:
                await process_checkpoint_batch()

        # Replace the original method
        state_manager.add_application_page = add_application_page_with_checkpoint

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
                    if await check_for_shutdown() or _force_exit_event.is_set():
                        state_manager.stop_crawler()
                        break

                    if url_queue.empty():
                        consecutive_empty_checks += 1
                        logger.info(
                            f"Queue appears empty (check {consecutive_empty_checks}/{EMPTY_THRESHOLD}), waiting to confirm..."
                        )

                        if consecutive_empty_checks >= EMPTY_THRESHOLD:
                            logger.info("Queue confirmed empty, crawling complete")
                            break
                        else:
                            # Wait a bit before checking again
                            await asyncio.sleep(5)
                            continue
                    else:
                        consecutive_empty_checks = 0  # Reset counter if queue has items

                    # Check URL limit
                    counters = await state_manager.get_counters()
                    if counters["visited"] >= Config.MAX_TOTAL_URLS:
                        logger.info(
                            f"Reached maximum total URLs limit ({Config.MAX_TOTAL_URLS})"
                        )
                        await state_manager.stop_crawler()
                        break

                    # Check for pending application pages that should be processed
                    if (
                        checkpoint_manager
                        and await checkpoint_manager.should_process_batch()
                    ):
                        await process_checkpoint_batch()

                    # Periodically save crawler state if checkpointing is enabled
                    if checkpoint_manager:
                        await checkpoint_manager.save_crawler_state(state_manager)

                    await asyncio.sleep(1)

                logger.info("Crawler reached completion criteria")

                # Process any remaining pending applications if checkpointing is enabled
                if checkpoint_manager:
                    await process_checkpoint_batch()

                # Give workers time to finish current tasks with timeout
                try:
                    await asyncio.wait_for(url_queue.join(), timeout=180)
                    logger.info("Queue joined successfully")
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for queue to empty")

            except asyncio.CancelledError:
                logger.info("Crawler task cancelled")
            except Exception as e:
                logger.error(f"Error in main crawl loop: {e}")
            finally:
                # Request workers to stop
                await state_manager.stop_crawler()

                # Cancel workers and monitor with a timeout
                for w in workers:
                    w.cancel()

                monitor_task.cancel()

                # Wait for cancellation to complete with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*workers, monitor_task, return_exceptions=True),
                        timeout=10,
                    )
                    logger.info("All tasks cancelled successfully")
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for tasks to cancel")

            # Explore specific application paths if admission domains were found
            admission_domains = await state_manager.get_admission_domains()
            if admission_domains and not _force_exit_event.is_set():
                logger.info(
                    "Exploring specific application paths on admission domains..."
                )
                try:
                    await asyncio.wait_for(
                        explore_specific_application_paths(), timeout=300
                    )
                except asyncio.TimeoutError:
                    logger.warning("Timeout exploring application paths")

            # Get all evaluated applications if checkpointing was used
            evaluated_results = []
            if checkpoint_manager:
                logger.info("Retrieving evaluated applications from checkpoints")
                evaluated_results = checkpoint_manager.get_all_evaluated_applications()
                if evaluated_results:
                    logger.info(
                        f"Retrieved {len(evaluated_results)} evaluated applications from checkpoints"
                    )

            # Process any remaining application pages
            found_applications = await state_manager.get_application_pages()
            # Remove any that have already been evaluated through checkpoints
            if evaluated_results and found_applications:
                evaluated_urls = {app.get("url") for app in evaluated_results}
                remaining_applications = [
                    app
                    for app in found_applications
                    if app.get("url") not in evaluated_urls
                ]
                logger.info(
                    f"Found {len(found_applications)} total application pages, {len(remaining_applications)} not yet evaluated"
                )
                found_applications = remaining_applications

            if (
                found_applications
                and not evaluated_results
                and not _force_exit_event.is_set()
            ):
                logger.info(
                    f"Found {len(found_applications)} potential application pages"
                )

                if not args.skip_evaluation:
                    try:
                        # Process with timeout
                        try:
                            evaluated_results = await asyncio.wait_for(
                                evaluate_all_applications(found_applications),
                                timeout=60,  # 1 minute timeout
                            )
                        except asyncio.TimeoutError:
                            logger.error(
                                "Timeout during evaluation, proceeding with partial results"
                            )
                            evaluated_results = found_applications

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
            elif not found_applications and not evaluated_results:
                logger.warning("No application pages found")

            # Save results
            try:
                os.makedirs(args.output_dir, exist_ok=True)

                # Use all application pages for original file
                all_found_applications = await state_manager.get_application_pages()

                # CORRECTION: Fix the result handling to properly handle the list of files
                saved_files = save_results(evaluated_applications=evaluated_results)
                logger.success(f"Results saved to {', '.join(saved_files)}")

                # Create a summary file variable for later use
                summary_file = None
                if saved_files and len(saved_files) >= 3:
                    summary_file = saved_files[
                        2
                    ]  # Assuming summary file is the third one
                else:
                    summary_file = None

                # Generate "How to Apply" report
                if evaluated_results and not _force_exit_event.is_set():
                    try:

                        md_file = os.path.join(
                            args.output_dir,
                            f"how_to_apply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        )
                        csv_file = os.path.join(
                            args.output_dir,
                            f"how_to_apply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        )
                        generate_how_to_apply_report(
                            evaluated_results, md_file, detailed=True
                        )
                        export_how_to_apply_csv(evaluated_results, csv_file)
                        logger.success(f"How to Apply report generated: {md_file}")
                        logger.success(f"How to Apply CSV generated: {csv_file}")
                    except Exception as e:
                        logger.error(f"Error generating How to Apply report: {e}")

                # Export to CSV if requested
                if args.csv and evaluated_results and not _force_exit_event.is_set():
                    try:

                        csv_file = os.path.join(
                            args.output_dir,
                            f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        )
                        export_to_csv(evaluated_results, csv_file)
                        logger.success(f"CSV export generated: {csv_file}")
                    except Exception as e:
                        logger.error(f"Error exporting to CSV: {e}")

            except Exception as e:
                logger.error(f"Error saving results: {e}")

            # Update database with final stats if enabled
            if Config.USE_SQLITE and not _force_exit_event.is_set():
                try:
                    counters = await state_manager.get_counters()
                    await end_crawl_run(
                        run_id,
                        counters["visited"],
                        (
                            len(all_found_applications)
                            if "all_found_applications" in locals()
                            else 0
                        ),
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
        # Final cleanup
        try:
            # Close the database connection
            if Config.USE_SQLITE:
                await close_connection()
                logger.info("Database connection closed")

            # Shutdown the thread pool executor
            api_executor.shutdown(wait=False)
            logger.info("Thread pool executor shutdown requested")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        logger.success(f"Crawler run {run_id} completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
        # If we've reached here, the program has exited normally
        logger.info("Program finished gracefully")

    except KeyboardInterrupt:
        logger.warning("\nProgram stopped by user")
        # Force exit after keyboard interrupt to ensure termination
        if not _force_exit_event.is_set():
            logger.warning("Forcing program termination...")
            os._exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)
