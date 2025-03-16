"""
Simplified report generator focused on clear 'How to Apply' instructions for each university
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

from loguru import logger


def generate_how_to_apply_report(evaluated_applications, output_file, detailed=False):
    """
    Generate a clear, focused report on how to apply to each university.

    Args:
        evaluated_applications: List of evaluated application pages
        output_file: Path to save the report
        detailed: Whether to include detailed analysis (default: False)

    Returns:
        str: Path to the generated report
    """
    # Group applications by university
    universities = {}
    for app in evaluated_applications:
        univ_name = app.get("university", "Unknown University")
        if univ_name not in universities:
            universities[univ_name] = []
        universities[univ_name].append(app)

    with open(output_file, "w") as f:
        f.write("# HOW TO APPLY - UNIVERSITY APPLICATION GUIDE\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Table of Contents\n\n")

        # Generate table of contents
        for univ_name in sorted(universities.keys()):
            f.write(f"- [{univ_name}](#{univ_name.lower().replace(' ', '-')})\n")

        f.write("\n---\n\n")

        # Process each university
        for univ_name in sorted(universities.keys()):
            apps = universities[univ_name]

            # Find the best application pages
            direct_apps = [
                a
                for a in apps
                if a.get("application_type") == "direct_application"
                and a.get("is_actual_application", False)
            ]
            external_apps = [
                a
                for a in apps
                if a.get("application_type") == "external_application_reference"
                and a.get("is_actual_application", False)
            ]
            info_apps = [
                a
                for a in apps
                if a.get("application_type")
                in ["application_instructions", "information_only"]
            ]

            # Write university section
            f.write(f"## {univ_name}\n\n")

            # Write summary recommendation
            f.write("### How to Apply\n\n")

            if direct_apps:
                # University has its own application portal
                best_app = direct_apps[0]  # Take the first one as an example
                f.write(
                    f"**Application Method**: Direct application through university portal\n\n"
                )
                f.write(
                    f"**Application Link**: [{best_app.get('title', 'Application Portal')}]({best_app.get('url')})\n\n"
                )

                # Extract domain for clarity
                domain = urlparse(best_app.get("url")).netloc
                f.write(
                    f"Apply directly through the university's application portal at {domain}.\n\n"
                )

                # Add any explanation from AI
                if "ai_evaluation" in best_app and best_app["ai_evaluation"]:
                    f.write(f"**Details**: {best_app['ai_evaluation']}\n\n")

            elif external_apps:
                # University uses external application system(s)
                best_app = external_apps[0]

                # Check if we have detected external systems
                if (
                    "external_application_systems" in best_app
                    and best_app["external_application_systems"]
                ):
                    systems = best_app["external_application_systems"]
                    f.write(
                        f"**Application Method**: External application system ({systems[0]['system_name']})\n\n"
                    )
                    f.write(
                        f"**Reference Page**: [{best_app.get('title', 'Application Information')}]({best_app.get('url')})\n\n"
                    )

                    # Add system-specific information
                    f.write(
                        f"Apply through {systems[0]['system_name']} at [{systems[0]['base_url']}]({systems[0]['base_url']})\n\n"
                    )

                    if "institution_code" in best_app and best_app["institution_code"]:
                        f.write(
                            f"**Institution Code**: {best_app['institution_code']}\n\n"
                        )

                else:
                    f.write(f"**Application Method**: External application system\n\n")
                    f.write(
                        f"**Reference Page**: [{best_app.get('title', 'Application Information')}]({best_app.get('url')})\n\n"
                    )
                    f.write(
                        "Visit the reference page for details on how to apply through the external system.\n\n"
                    )

                # Add any explanation from AI
                if "ai_evaluation" in best_app and best_app["ai_evaluation"]:
                    f.write(f"**Details**: {best_app['ai_evaluation']}\n\n")

            elif info_apps:
                # Only have information pages
                best_app = info_apps[0]
                f.write(f"**Application Method**: See information page\n\n")
                f.write(
                    f"**Information Page**: [{best_app.get('title', 'Application Information')}]({best_app.get('url')})\n\n"
                )
                f.write(
                    "Refer to the information page for application instructions.\n\n"
                )

            else:
                # No clear application pages found
                f.write("**Application Method**: Unknown\n\n")
                f.write(
                    "No clear application information was found. Visit the university's main website.\n\n"
                )

            # Additional resources section
            if detailed:
                f.write("### Additional Resources\n\n")

                # List all application-related pages found
                if direct_apps:
                    f.write("#### Direct Application Portals\n\n")
                    for app in direct_apps:
                        f.write(
                            f"- [{app.get('title', 'Application Portal')}]({app.get('url')})\n"
                        )
                    f.write("\n")

                if external_apps:
                    f.write("#### External Application References\n\n")
                    for app in external_apps:
                        f.write(
                            f"- [{app.get('title', 'External System Reference')}]({app.get('url')})\n"
                        )
                    f.write("\n")

                if info_apps:
                    f.write("#### Information Pages\n\n")
                    for app in info_apps[:5]:  # Limit to top 5 to avoid clutter
                        f.write(
                            f"- [{app.get('title', 'Information Page')}]({app.get('url')})\n"
                        )
                    f.write("\n")

            f.write("---\n\n")

    logger.success(f"Generated How to Apply report at {output_file}")
    return output_file


def export_how_to_apply_csv(evaluated_applications, output_file):
    """
    Export a simplified CSV with clear application instructions for each university

    Args:
        evaluated_applications: List of evaluated application pages
        output_file: Path to save the CSV

    Returns:
        str: Path to the generated CSV
    """
    # Group applications by university
    universities = {}
    for app in evaluated_applications:
        univ_name = app.get("university", "Unknown University")
        if univ_name not in universities:
            universities[univ_name] = []
        universities[univ_name].append(app)

    # Prepare data for CSV
    rows = []

    for univ_name, apps in universities.items():
        # Find the best application pages
        direct_apps = [
            a
            for a in apps
            if a.get("application_type") == "direct_application"
            and a.get("is_actual_application", False)
        ]
        external_apps = [
            a
            for a in apps
            if a.get("application_type") == "external_application_reference"
            and a.get("is_actual_application", False)
        ]
        info_apps = [
            a
            for a in apps
            if a.get("application_type")
            in ["application_instructions", "information_only"]
        ]

        row = {
            "University": univ_name,
            "Application Method": "",
            "Primary URL": "",
            "Portal/System": "",
            "Institution Code": "",
            "Additional Details": "",
        }

        if direct_apps:
            best_app = direct_apps[0]
            row["Application Method"] = "Direct application through university portal"
            row["Primary URL"] = best_app.get("url", "")
            row["Portal/System"] = urlparse(best_app.get("url")).netloc
            row["Additional Details"] = (
                best_app.get("ai_evaluation", "")[:200] + "..."
                if best_app.get("ai_evaluation", "")
                else ""
            )

        elif external_apps:
            best_app = external_apps[0]

            if (
                "external_application_systems" in best_app
                and best_app["external_application_systems"]
            ):
                systems = best_app["external_application_systems"]
                row["Application Method"] = (
                    f"External application system ({systems[0]['system_name']})"
                )
                row["Primary URL"] = best_app.get("url", "")
                row["Portal/System"] = systems[0]["base_url"]
                row["Institution Code"] = best_app.get("institution_code", "")
                row["Additional Details"] = (
                    best_app.get("ai_evaluation", "")[:200] + "..."
                    if best_app.get("ai_evaluation", "")
                    else ""
                )
            else:
                row["Application Method"] = "External application system"
                row["Primary URL"] = best_app.get("url", "")
                row["Additional Details"] = (
                    best_app.get("ai_evaluation", "")[:200] + "..."
                    if best_app.get("ai_evaluation", "")
                    else ""
                )

        elif info_apps:
            best_app = info_apps[0]
            row["Application Method"] = "See information page"
            row["Primary URL"] = best_app.get("url", "")
            row["Additional Details"] = (
                best_app.get("ai_evaluation", "")[:200] + "..."
                if best_app.get("ai_evaluation", "")
                else ""
            )

        else:
            row["Application Method"] = "Unknown"
            row["Additional Details"] = "No clear application information found"

        rows.append(row)

    # Write to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "University",
                "Application Method",
                "Primary URL",
                "Portal/System",
                "Institution Code",
                "Additional Details",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.success(f"Generated How to Apply CSV at {output_file}")
    return output_file
