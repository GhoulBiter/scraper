"""
Exporter for crawler results
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from loguru import logger
from models.application_page import ApplicationPage, ApplicationPageCollection


def save_results(
    found_applications: List[Dict],
    evaluated_applications: Optional[List[Dict]] = None,
    api_metrics: Optional[Dict] = None,
    output_dir: str = "outputs",
) -> Tuple[str, Optional[str], Optional[str]]:
    """Save crawler results to JSON files and generate summary."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Convert to ApplicationPage collection and save original results
    original_collection = ApplicationPageCollection.from_dict_list(found_applications)
    original_filename = os.path.join(output_dir, f"application_pages_{timestamp}.json")
    with open(original_filename, "w") as f:
        json.dump(original_collection.to_dict_list(), f, indent=2)

    logger.info(f"Original results saved to {original_filename}")

    # Save evaluated results if available
    evaluated_filename = None
    summary_file = None

    if evaluated_applications:
        # Convert to ApplicationPage collection
        evaluated_collection = ApplicationPageCollection.from_dict_list(
            evaluated_applications
        )

        evaluated_filename = os.path.join(
            output_dir, f"evaluated_applications_{timestamp}.json"
        )
        with open(evaluated_filename, "w") as f:
            json.dump(evaluated_collection.to_dict_list(), f, indent=2)

        logger.info(f"Evaluated results saved to {evaluated_filename}")

        # Generate summary report
        summary_file = os.path.join(output_dir, f"summary_{timestamp}.txt")
        generate_summary_report(evaluated_collection, summary_file, api_metrics)

        logger.info(f"Summary saved to {summary_file}")

    return original_filename, evaluated_filename, summary_file


def generate_summary_report(
    evaluated_collection: ApplicationPageCollection,
    output_file: str,
    api_metrics: Optional[Dict] = None,
) -> None:
    """Generate a summary report of the findings."""

    # Get actual application pages
    actual_apps = evaluated_collection.filter_actual_applications()

    # Group by university
    by_university = evaluated_collection.group_by_university()

    # Get unique universities
    universities_visited = list(by_university.keys())

    with open(output_file, "w") as f:
        # Add API metrics if available
        if api_metrics:
            f.write("=== API Usage Metrics ===\n\n")
            f.write(f"Model: {api_metrics.get('model', 'Unknown')}\n")
            f.write(f"Pages evaluated: {api_metrics.get('pages_evaluated', 0)}\n")
            f.write(f"Prompt tokens: {api_metrics.get('prompt_tokens', 0)}\n")
            f.write(f"Completion tokens: {api_metrics.get('completion_tokens', 0)}\n")
            f.write(f"Total tokens: {api_metrics.get('total_tokens', 0)}\n")
            f.write(
                f"Estimated cost: ${api_metrics.get('estimated_cost_usd', 0.0):.4f} USD\n\n"
            )

        # Main summary
        f.write("=== University Application Pages Summary ===\n\n")
        f.write(f"Universities Visited: {', '.join(universities_visited)}\n")
        f.write(f"Total application pages found: {len(evaluated_collection.pages)}\n")
        f.write(f"Actual application pages (AI evaluated): {len(actual_apps)}\n\n")

        # Details by university
        for univ, apps in by_university.items():
            f.write(f"== {univ}: {len(apps)} application pages ==\n")

            # First list actual application pages
            f.write("\n--- ACTUAL APPLICATION PAGES ---\n")
            actual_apps = [app for app in apps if app.is_actual_application]
            for i, app in enumerate(actual_apps, 1):
                f.write(
                    f"{i}. {app.title}\n   {app.url}\n   Evaluation: {app.ai_evaluation}\n\n"
                )

            # Then list information/other pages
            f.write("\n--- INFORMATION/OTHER PAGES ---\n")
            info_apps = [app for app in apps if not app.is_actual_application]
            for i, app in enumerate(info_apps, 1):
                f.write(
                    f"{i}. {app.title}\n   {app.url}\n   Evaluation: {app.ai_evaluation}\n\n"
                )


def export_to_csv(applications: List[Dict], output_file: str) -> None:
    """Export application pages to CSV format."""
    # Convert to ApplicationPage collection
    app_collection = ApplicationPageCollection.from_dict_list(applications)

    # Define fields to include
    fields = [
        "url",
        "title",
        "university",
        "is_actual_application",
        "ai_evaluation",
        "depth",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for app in app_collection.pages:
            # Convert ApplicationPage to dict
            app_dict = app.to_dict()

            # Create a row with just the fields we want
            row = {field: app_dict.get(field, "") for field in fields}

            # Convert boolean to string value
            if "is_actual_application" in row:
                row["is_actual_application"] = (
                    "Yes" if row["is_actual_application"] else "No"
                )

            writer.writerow(row)

    logger.info(
        f"Exported {len(app_collection.pages)} application pages to {output_file}"
    )


def update_metrics_in_summary(
    summary_file: str, api_metrics: Dict, historical_metrics: Optional[Dict] = None
) -> None:
    """Add or update API metrics in an existing summary file."""
    if not os.path.exists(summary_file):
        logger.warning(f"Summary file {summary_file} does not exist")
        return

    # Create a temporary file with metrics
    temp_metrics_file = f"temp_metrics_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    try:
        with open(temp_metrics_file, "w") as f:
            f.write("=== API Usage Metrics ===\n\n")
            f.write(f"Model: {api_metrics.get('model', 'Unknown')}\n")
            f.write(f"Pages evaluated: {api_metrics.get('pages_evaluated', 0)}\n")
            f.write(f"Prompt tokens: {api_metrics.get('prompt_tokens', 0)}\n")
            f.write(f"Completion tokens: {api_metrics.get('completion_tokens', 0)}\n")
            f.write(f"Total tokens: {api_metrics.get('total_tokens', 0)}\n")
            f.write(
                f"Estimated cost: ${api_metrics.get('estimated_cost_usd', 0.0):.4f} USD\n\n"
            )

            # Add historical metrics if available
            if historical_metrics:
                f.write("=== Historical API Usage (Last 30 Days) ===\n\n")
                f.write(f"Total runs: {historical_metrics.get('total_runs', 0)}\n")
                f.write(
                    f"Total pages evaluated: {historical_metrics.get('total_pages', 0)}\n"
                )
                f.write(
                    f"Total tokens used: {historical_metrics.get('total_tokens', 0)}\n"
                )
                f.write(
                    f"Total estimated cost: ${historical_metrics.get('total_cost', 0.0):.4f} USD\n\n"
                )

        # Now combine the metrics file with the original summary
        with open(summary_file, "r") as original:
            original_content = original.read()

        with open(summary_file, "w") as final:
            with open(temp_metrics_file, "r") as metrics:
                metrics_content = metrics.read()
            final.write(metrics_content)
            final.write(original_content)

        # Remove the temporary file
        os.remove(temp_metrics_file)

        logger.success(f"Added API metrics to summary file {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write API metrics to summary file: {e}")

        # Clean up temp file if it exists
        if os.path.exists(temp_metrics_file):
            try:
                os.remove(temp_metrics_file)
            except:
                pass
