"""
Improved report generator focused on undergraduate applications with special case handling
"""

import os
import csv
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

from loguru import logger
from output.special_cases import (
    EXTERNAL_APPLICATION_SYSTEMS,
    get_special_case_for_university,
    get_special_case_for_domain,
    is_undergraduate_page,
)


def detect_external_system(page):
    """
    Detect which external application system is mentioned in the page.

    Args:
        page: The application page dictionary

    Returns:
        dict or None: Information about the detected external system
    """
    university_name = page.get("university", "")
    url = page.get("url", "")

    # First check if there's a special case for this university
    special_case = get_special_case_for_university(university_name)
    if special_case:
        system_key = special_case.get("system")
        if system_key and system_key in EXTERNAL_APPLICATION_SYSTEMS:
            return {
                "system": system_key,
                "name": EXTERNAL_APPLICATION_SYSTEMS[system_key]["name"],
                "url": special_case.get(
                    "application_portal",
                    EXTERNAL_APPLICATION_SYSTEMS[system_key]["url"],
                ),
                "note": special_case.get("note", ""),
                "institution_code": special_case.get("institution_code", ""),
            }

    # Then check if there's a special case for the domain
    domain_case = get_special_case_for_domain(url)
    if domain_case:
        system_key = domain_case.get("system")
        if system_key and system_key in EXTERNAL_APPLICATION_SYSTEMS:
            return {
                "system": system_key,
                "name": EXTERNAL_APPLICATION_SYSTEMS[system_key]["name"],
                "url": domain_case.get(
                    "application_portal",
                    EXTERNAL_APPLICATION_SYSTEMS[system_key]["url"],
                ),
                "note": domain_case.get("note", ""),
            }

    # Check for detected external systems from AI evaluation
    if "detected_external_systems" in page:
        for system in page["detected_external_systems"]:
            if system in EXTERNAL_APPLICATION_SYSTEMS:
                return {
                    "system": system,
                    "name": EXTERNAL_APPLICATION_SYSTEMS[system]["name"],
                    "url": EXTERNAL_APPLICATION_SYSTEMS[system]["url"],
                    "description": EXTERNAL_APPLICATION_SYSTEMS[system].get(
                        "description", ""
                    ),
                }

    # Check for external application systems in external_application_systems
    if "external_application_systems" in page and page["external_application_systems"]:
        systems = page["external_application_systems"]
        if systems and len(systems) > 0:
            system_name = systems[0].get("system_name", "").lower()
            # Try to map to our standardized systems
            for key, info in EXTERNAL_APPLICATION_SYSTEMS.items():
                if key.lower() in system_name or info["name"].lower() in system_name:
                    return {
                        "system": key,
                        "name": info["name"],
                        "url": info["url"],
                        "description": info.get("description", ""),
                    }

            # If no match, just return what we have
            return {
                "system": systems[0].get("system_name", ""),
                "name": systems[0].get("system_name", ""),
                "url": systems[0].get("base_url", ""),
            }

    # Check AI evaluation text for mentions of systems
    if "ai_evaluation" in page:
        evaluation = page["ai_evaluation"].lower()

        # Look for mentions of major application systems
        for system, info in EXTERNAL_APPLICATION_SYSTEMS.items():
            # Create a more specific pattern to avoid false positives
            system_name = info["name"].lower()
            if system in evaluation or system_name in evaluation:
                return {
                    "system": system,
                    "name": info["name"],
                    "url": info["url"],
                    "description": info.get("description", ""),
                }

    # No external system detected
    return None


def find_best_application_page(pages, university_name):
    """
    Find the best application page for a university, prioritizing undergraduate pages.

    Args:
        pages: List of application pages for the university
        university_name: Name of the university

    Returns:
        dict: Best application page
    """
    # Filter for undergraduate pages only
    undergrad_pages = [p for p in pages if is_undergraduate_page(p)]
    if not undergrad_pages:
        return None

    # Prioritize actual application pages
    actual_apps = [p for p in undergrad_pages if p.get("is_actual_application", False)]
    if not actual_apps:
        return undergrad_pages[
            0
        ]  # Return any undergraduate page if no actual app pages

    # Priority based on URL patterns
    priority_patterns = [
        "/apply/first-year",
        "/apply/freshman",
        "/apply/undergraduate",
        "/apply/transfer",
        "/admission/apply",
        "/admissions/apply",
        "/apply$",
        "/apply/$",
    ]

    for pattern in priority_patterns:
        for page in actual_apps:
            url = page.get("url", "")
            if re.search(pattern, url):
                return page

    # If no priority match, return first actual application page
    return actual_apps[0]


def generate_how_to_apply_report(evaluated_applications, output_file, detailed=False):
    """
    Generate a clear, focused report on how to apply to each university for undergraduate programs.

    Args:
        evaluated_applications: List of evaluated application pages
        output_file: Path to save the report
        detailed: Whether to include detailed analysis (default: False)

    Returns:
        str: Path to the generated report
    """
    # Filter out graduate-specific application pages
    undergrad_applications = [
        a for a in evaluated_applications if is_undergraduate_page(a)
    ]

    # Group applications by university
    universities = {}
    for app in undergrad_applications:
        univ_name = app.get("university", "Unknown University")
        if univ_name not in universities:
            universities[univ_name] = []
        universities[univ_name].append(app)

    with open(output_file, "w") as f:
        f.write("# HOW TO APPLY - UNIVERSITY UNDERGRADUATE APPLICATION GUIDE\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Table of Contents\n\n")

        # Generate table of contents
        for univ_name in sorted(universities.keys()):
            f.write(
                f"- [{univ_name}](#{univ_name.lower().replace(' ', '-').replace(',', '').replace('(', '').replace(')', '')})\n"
            )

        f.write("\n---\n\n")

        # Process each university
        for univ_name in sorted(universities.keys()):
            apps = universities[univ_name]

            # Find the best application page
            best_app = find_best_application_page(apps, univ_name)

            if not best_app:
                continue  # Skip if no undergraduate page found

            # Detect external application system
            external_system = detect_external_system(best_app)

            # Write university section
            f.write(f"## {univ_name}\n\n")

            # Write summary recommendation
            f.write("### How to Apply\n\n")

            if external_system:
                # University uses external application system
                f.write(
                    f"**Application Method**: External application system ({external_system['name']})\n\n"
                )
                f.write(
                    f"**Reference Page**: [{best_app.get('title', 'Application Information')}]({best_app.get('url')})\n\n"
                )
                f.write(
                    f"**External Application Portal**: [{external_system['name']}]({external_system['url']})\n\n"
                )

                if (
                    "institution_code" in external_system
                    and external_system["institution_code"]
                ):
                    f.write(
                        f"**Institution Code**: {external_system['institution_code']}\n\n"
                    )

                if "note" in external_system and external_system["note"]:
                    f.write(f"**Note**: {external_system['note']}\n\n")

                f.write(
                    f"Apply through {external_system['name']} at [{external_system['url']}]({external_system['url']}). Visit the reference page for specific requirements and deadlines.\n\n"
                )
            else:
                # University has its own application portal
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

            # Additional resources section
            if detailed:
                f.write("### Additional Resources\n\n")

                # List direct application portals
                direct_apps = [
                    a
                    for a in apps
                    if a.get("application_type") == "direct_application"
                    and a.get("is_actual_application", False)
                ]

                if direct_apps:
                    f.write("#### Direct Application Portals\n\n")
                    for app in direct_apps:
                        f.write(
                            f"- [{app.get('title', 'Application Portal')}]({app.get('url')})\n"
                        )
                    f.write("\n")

                # List external application references
                external_apps = [
                    a
                    for a in apps
                    if a.get("application_type") == "external_application_reference"
                    and a.get("is_actual_application", False)
                ]

                if external_apps:
                    f.write("#### External Application References\n\n")
                    for app in external_apps:
                        f.write(
                            f"- [{app.get('title', 'External System Reference')}]({app.get('url')})\n"
                        )
                    f.write("\n")

                # List information pages
                info_apps = [
                    a for a in apps if not a.get("is_actual_application", False)
                ]

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
    Export a simplified CSV with clear application instructions for undergraduate programs

    Args:
        evaluated_applications: List of evaluated application pages
        output_file: Path to save the CSV

    Returns:
        str: Path to the generated CSV
    """
    # Filter out graduate-specific application pages
    undergrad_applications = [
        a for a in evaluated_applications if is_undergraduate_page(a)
    ]

    # Group applications by university
    universities = {}
    for app in undergrad_applications:
        univ_name = app.get("university", "Unknown University")
        if univ_name not in universities:
            universities[univ_name] = []
        universities[univ_name].append(app)

    # Prepare data for CSV
    rows = []

    for univ_name, apps in universities.items():
        # Find the best application page
        best_app = find_best_application_page(apps, univ_name)

        if not best_app:
            continue  # Skip if no undergraduate page found

        # Detect external application system
        external_system = detect_external_system(best_app)

        row = {
            "University": univ_name,
            "Application Method": "",
            "Reference Page": "",
            "Application Portal": "",
            "External System": "",
            "Institution Code": "",
            "Notes": "",
        }

        if external_system:
            row["Application Method"] = f"External system: {external_system['name']}"
            row["Reference Page"] = best_app.get("url", "")
            row["External System"] = external_system["url"]
            if (
                "institution_code" in external_system
                and external_system["institution_code"]
            ):
                row["Institution Code"] = external_system["institution_code"]
            if "note" in external_system and external_system["note"]:
                row["Notes"] = external_system["note"]
        else:
            row["Application Method"] = "Direct university portal"
            row["Application Portal"] = best_app.get("url", "")

        # Add a brief excerpt from AI evaluation
        if "ai_evaluation" in best_app and best_app["ai_evaluation"]:
            excerpt = best_app["ai_evaluation"]
            if len(excerpt) > 200:
                excerpt = excerpt[:197] + "..."

            if row["Notes"]:
                row["Notes"] += " " + excerpt
            else:
                row["Notes"] = excerpt

        rows.append(row)

    # Write to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "University",
                "Application Method",
                "Reference Page",
                "Application Portal",
                "External System",
                "Institution Code",
                "Notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.success(f"Generated How to Apply CSV at {output_file}")
    return output_file
