"""
Functions to generate URLs for external application systems
"""

import re

from analysis.page_analyzer import EXTERNAL_APPLICATION_SYSTEMS


# Base URLs for common external application systems
APPLICATION_SYSTEM_URLS = {
    "ucas": "https://www.ucas.com/apply",
    "common_app": "https://apply.commonapp.org/login",
    "coalition": "https://app.commonapp.org/apply/coalition",
    "applytexas": "https://www.applytexas.org/adappc/gen/c_start.WBX",
    "cal_state": "https://www.calstate.edu/apply",
    "ouac": "https://www.ouac.on.ca/apply/",
    "uac": "https://www5.uac.edu.au/uacug/",
    "studylink": "https://www.studylink.govt.nz/apply/",
    "uni_assist": "https://www.uni-assist.de/en/how-to-apply/",
    "postgrad": "https://graduateadmissions.herokuapp.com/",  # Generic placeholder for graduate systems
}


# Advanced URL construction for systems that need institution-specific parameters
def get_system_url(
    system_name, university=None, program_code=None, institution_code=None
):
    """
    Generate a URL for an external application system, with optional parameters for
    university-specific links.

    Args:
        system_name (str): The name of the external application system
        university (str, optional): University name for system-specific URLs
        program_code (str, optional): Program code for certain application systems
        institution_code (str, optional): Institution code for certain application systems

    Returns:
        dict: A dictionary containing the system name, base URL, and any additional information
    """

    # Initialize result dictionary
    result = {
        "system_name": system_name,
        "base_url": APPLICATION_SYSTEM_URLS.get(system_name.lower(), ""),
        "university_specific_url": None,
        "additional_info": None,
    }

    # Handle system-specific URL construction
    if system_name.lower() == "ucas" and institution_code:
        result["additional_info"] = f"UCAS Institution Code: {institution_code}"
        if program_code:
            result["additional_info"] += f", Program Code: {program_code}"

    elif system_name.lower() == "common_app" and university:
        # Format university name for potential search parameter
        univ_param = university.lower().replace(" ", "-")
        result["university_specific_url"] = f"{result['base_url']}?search={univ_param}"

    elif system_name.lower() == "applytexas" and institution_code:
        result["additional_info"] = f"ApplyTexas Institution Code: {institution_code}"

    elif system_name.lower() == "ouac" and university:
        # OUAC has different application paths (101 for undergrad, 105 for transfer, etc.)
        result["base_url"] = "https://www.ouac.on.ca/apply/"
        result["additional_info"] = (
            "You may need to select the appropriate OUAC form (101, 105, etc.)"
        )

    # Return the constructed result
    return result


def extract_application_system_from_html(html, url, university_name):
    """
    Extract external application system references from HTML content
    and generate appropriate application URLs.

    Args:
        html (str): The HTML content of the page
        url (str): The URL of the page
        university_name (str): The name of the university

    Returns:
        list: List of dictionaries containing application system information
    """

    results = []
    html_lower = html.lower()

    # Extract potential institution codes
    institution_code = None
    program_code = None

    # Look for institution codes (common formats)
    inst_code_patterns = [
        r"institution code:?\s*([A-Z0-9]{4,6})",
        r"college code:?\s*([A-Z0-9]{4,6})",
        r"university code:?\s*([A-Z0-9]{4,6})",
        r"ucas code:?\s*([A-Z0-9]{4,6})",
    ]

    for pattern in inst_code_patterns:
        code_match = re.search(pattern, html_lower)
        if code_match:
            institution_code = code_match.group(1).upper()
            break

    # Look for program codes
    prog_code_patterns = [
        r"program code:?\s*([A-Z0-9]{3,8})",
        r"course code:?\s*([A-Z0-9]{3,8})",
    ]

    for pattern in prog_code_patterns:
        code_match = re.search(pattern, html_lower)
        if code_match:
            program_code = code_match.group(1).upper()
            break

    # Check for each application system
    for system, identifiers in EXTERNAL_APPLICATION_SYSTEMS.items():
        for identifier in identifiers:
            if identifier in html_lower:
                # Create a system URL result
                system_url_info = get_system_url(
                    system,
                    university=university_name,
                    program_code=program_code,
                    institution_code=institution_code,
                )

                # Add the reference that was found
                system_url_info["found_reference"] = identifier

                # Add to results if not already present
                if not any(r["system_name"] == system for r in results):
                    results.append(system_url_info)

    return results
