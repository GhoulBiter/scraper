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
from output.how_to_apply_report import (
    generate_how_to_apply_report,
    export_how_to_apply_csv,
)


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
    evaluated_applications: List[Dict],
    output_file: str,
    api_metrics: Optional[Dict] = None,
) -> None:
    """Generate a summary report of the findings with categorization."""

    # Handle both dictionaries and ApplicationPage objects
    def get_value(app, field, default=None):
        if isinstance(app, dict):
            return app.get(field, default)
        else:
            return getattr(app, field, default)

    # Count by category
    category_counts = {
        "direct_application": 0,
        "application_instructions": 0,
        "external_application_reference": 0,
        "information_only": 0,
    }

    for app in evaluated_applications:
        app_type = get_value(app, "application_type", "information_only")
        if app_type in category_counts:
            category_counts[app_type] += 1

    # Get unique universities visited
    universities_visited = list(
        set(get_value(app, "university") for app in evaluated_applications)
    )

    # Group by university
    by_university = {}
    for app in evaluated_applications:
        univ = get_value(app, "university")
        if univ not in by_university:
            by_university[univ] = []
        by_university[univ].append(app)

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
        f.write(f"Total application pages found: {len(evaluated_applications)}\n")

        # Breakdown by category
        f.write("\n=== Pages by Category ===\n")
        f.write(f"Direct Application Pages: {category_counts['direct_application']}\n")
        f.write(
            f"Application Instructions Pages: {category_counts['application_instructions']}\n"
        )
        f.write(
            f"External Application References: {category_counts['external_application_reference']}\n"
        )
        f.write(f"Information Only Pages: {category_counts['information_only']}\n\n")

        # Details by university
        for univ, apps in by_university.items():
            f.write(f"== {univ}: {len(apps)} application pages ==\n")

            # Group by category for this university
            categories = {
                "direct_application": [],
                "application_instructions": [],
                "external_application_reference": [],
                "information_only": [],
            }

            for app in apps:
                app_type = get_value(app, "application_type", "information_only")
                if app_type in categories:
                    categories[app_type].append(app)

            # Direct application pages
            if categories["direct_application"]:
                f.write("\n--- DIRECT APPLICATION PAGES ---\n")
                for i, app in enumerate(categories["direct_application"], 1):
                    f.write(
                        f"{i}. {get_value(app, 'title')}\n   {get_value(app, 'url')}\n   Evaluation: {get_value(app, 'ai_evaluation')}\n\n"
                    )

            # Application instructions
            if categories["application_instructions"]:
                f.write("\n--- APPLICATION INSTRUCTIONS PAGES ---\n")
                for i, app in enumerate(categories["application_instructions"], 1):
                    f.write(
                        f"{i}. {get_value(app, 'title')}\n   {get_value(app, 'url')}\n   Evaluation: {get_value(app, 'ai_evaluation')}\n\n"
                    )

            # External application references
            if categories["external_application_reference"]:
                f.write("\n--- EXTERNAL APPLICATION REFERENCES ---\n")
                for i, app in enumerate(
                    categories["external_application_reference"], 1
                ):
                    f.write(
                        f"{i}. {get_value(app, 'title')}\n   {get_value(app, 'url')}\n   Evaluation: {get_value(app, 'ai_evaluation')}\n\n"
                    )

            # Information only pages
            if categories["information_only"]:
                f.write("\n--- INFORMATION ONLY PAGES ---\n")
                for i, app in enumerate(categories["information_only"], 1):
                    f.write(
                        f"{i}. {get_value(app, 'title')}\n   {get_value(app, 'url')}\n   Evaluation: {get_value(app, 'ai_evaluation')}\n\n"
                    )


def export_to_csv(applications: List[Any], output_file: str) -> None:
    """Export application pages to CSV format with categorization."""
    # Define fields to include
    fields = [
        "url",
        "title",
        "university",
        "is_actual_application",
        "application_type",
        "category",
        "ai_evaluation",
        "depth",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for app in applications:
            # Handle both dictionaries and ApplicationPage objects
            if isinstance(app, dict):
                # Create a row with just the fields we want
                row = {field: app.get(field, "") for field in fields}
            else:
                # It's an ApplicationPage object
                row = {field: getattr(app, field, "") for field in fields}

            # Convert boolean to string value
            if "is_actual_application" in row:
                row["is_actual_application"] = (
                    "Yes" if row["is_actual_application"] else "No"
                )

            # Convert category number to a more readable form if it's an integer
            if "category" in row and isinstance(row["category"], int):
                category_map = {
                    1: "Direct Application",
                    2: "Instructions",
                    3: "External Reference",
                    4: "Information Only",
                }
                row["category"] = category_map.get(row["category"], row["category"])

            writer.writerow(row)

    logger.info(f"Exported {len(applications)} application pages to {output_file}")


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


def save_how_to_apply_report(
    evaluated_applications, output_dir="outputs", detailed=False
):
    """
    Generate and save a focused 'How to Apply' report

    Args:
        evaluated_applications: List of evaluated application pages
        output_dir: Directory to save the report
        detailed: Whether to include detailed analysis

    Returns:
        tuple: Paths to the generated report files (markdown, csv)
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate markdown report
    md_file = os.path.join(output_dir, f"how_to_apply_{timestamp}.md")
    generate_how_to_apply_report(evaluated_applications, md_file, detailed=detailed)

    # Generate CSV
    csv_file = os.path.join(output_dir, f"how_to_apply_{timestamp}.csv")
    export_how_to_apply_csv(evaluated_applications, csv_file)

    logger.success(f"How to Apply reports saved to {output_dir}")
    return md_file, csv_file
