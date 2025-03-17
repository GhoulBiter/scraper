# Dictionary of known external application systems with their official URLs
import re
from output.special_cases import DOMAIN_PATTERNS, UNIVERSITY_SPECIAL_CASES


EXTERNAL_APPLICATION_SYSTEMS = {
    "ucas": {
        "name": "UCAS (Universities and Colleges Admissions Service)",
        "url": "https://www.ucas.com/apply",
        "description": "The central application service for UK undergraduate programs",
    },
    "common_app": {
        "name": "Common Application",
        "url": "https://apply.commonapp.org/login",
        "description": "Application platform for over 900 colleges and universities, primarily in the US",
    },
    "coalition": {
        "name": "Coalition Application",
        "url": "https://app.coalitionforcollegeaccess.org/",
        "description": "Alternative to Common App, used by about 150 US colleges and universities",
    },
    "uc_application": {
        "name": "University of California Application",
        "url": "https://apply.universityofcalifornia.edu/my-application/login",
        "description": "Central application for all University of California campuses",
    },
    "cal_state_apply": {
        "name": "Cal State Apply",
        "url": "https://www.calstate.edu/apply",
        "description": "Application portal for all California State University campuses",
    },
    "applytexas": {
        "name": "ApplyTexas",
        "url": "https://www.applytexas.org/adappc/gen/c_start.WBX",
        "description": "Application system for Texas public universities and community colleges",
    },
    "ouac": {
        "name": "Ontario Universities' Application Centre",
        "url": "https://www.ouac.on.ca/apply/",
        "description": "Central application service for universities in Ontario, Canada",
    },
    "uac": {
        "name": "Universities Admissions Centre (Australia)",
        "url": "https://www5.uac.edu.au/uacug/",
        "description": "Central admissions for undergraduate study at participating institutions in NSW and ACT, Australia",
    },
    "studylink": {
        "name": "StudyLink (New Zealand)",
        "url": "https://www.studylink.govt.nz/apply/",
        "description": "New Zealand's student loan and allowance application system",
    },
    "uni_assist": {
        "name": "uni-assist (Germany)",
        "url": "https://www.uni-assist.de/en/how-to-apply/",
        "description": "Application service for international students applying to German universities",
    },
}


def get_system_url(
    system_name, university=None, program_code=None, institution_code=None
):
    """
    Generate a URL for an external application system, with optional parameters.
    Centralized version of the function previously duplicated across modules.

    Args:
        system_name (str): The name of the external application system
        university (str, optional): University name for system-specific URLs
        program_code (str, optional): Program code for certain application systems
        institution_code (str, optional): Institution code for certain application systems

    Returns:
        dict: A dictionary containing the system name, base URL, and any additional information
    """
    # Normalize system name
    system_name = system_name.lower().replace(" ", "_").replace("-", "_")

    # Check for direct match in external application systems
    if system_name in EXTERNAL_APPLICATION_SYSTEMS:
        system_info = EXTERNAL_APPLICATION_SYSTEMS[system_name]

        result = {
            "system_name": system_name,
            "name": system_info["name"],
            "base_url": system_info["url"],
            "description": system_info.get("description", ""),
            "university_specific_url": None,
            "additional_info": None,
        }

        # Handle system-specific URL construction
        if system_name == "ucas" and institution_code:
            result["additional_info"] = f"UCAS Institution Code: {institution_code}"
            if program_code:
                result["additional_info"] += f", Program Code: {program_code}"

        elif system_name == "common_app" and university:
            # Format university name for search parameter
            univ_param = university.lower().replace(" ", "-")
            result["university_specific_url"] = (
                f"{result['base_url']}?search={univ_param}"
            )

        elif system_name == "applytexas" and institution_code:
            result["additional_info"] = (
                f"ApplyTexas Institution Code: {institution_code}"
            )

        elif system_name == "ouac" and university:
            # OUAC has different application paths (101 for undergrad, 105 for transfer, etc.)
            result["base_url"] = "https://www.ouac.on.ca/apply/"
            result["additional_info"] = (
                "You may need to select the appropriate OUAC form (101, 105, etc.)"
            )

        # Add application steps if available
        if "application_steps" in system_info:
            result["application_steps"] = system_info.get("application_steps", [])

        # Add institution-specific search URL if applicable and university is provided
        if university and "search_url" in system_info:
            search_param = university.lower().replace(" ", "+")
            result["institution_search_url"] = (
                f"{system_info.get('search_url', '')}?q={search_param}"
            )

        return result

    # Handle aliases and partial matches
    system_aliases = {
        "ucas": ["ucas", "uk", "uk_application", "uk_undergrad"],
        "common_app": ["common", "commonapp", "common_application"],
        "coalition": ["coalition_app", "mycoalition"],
        "applytexas": ["texas", "apply_texas"],
        "cal_state_apply": ["csu", "calstate", "california_state"],
        "uc_application": ["uc", "university_of_california", "uc_application"],
        "ouac": ["ontario", "ontario_application"],
        "uac": ["australia", "australian", "nsw"],
        "uni_assist": ["germany", "german", "uniassist"],
    }

    # Check for system aliases
    for system, aliases in system_aliases.items():
        if system_name in aliases and system in EXTERNAL_APPLICATION_SYSTEMS:
            # Recursively call with the canonical system name
            return get_system_url(system, university, program_code, institution_code)

    # Return a general guide if no specific system is found
    return {
        "system_name": system_name,
        "name": "General Application Guide",
        "base_url": "",
        "description": "No specific information found for this application system",
        "general_steps": [
            "Check the university's official website for application instructions",
            "Note application deadlines and requirements",
            "Prepare necessary documents (transcripts, test scores, etc.)",
            "Complete and submit application form",
            "Pay application fee if required",
            "Check application status regularly",
        ],
    }


def detect_application_system(url=None, html_content=None, university_name=None):
    """
    Detect which external application system is mentioned in a page.
    Centralized version of detection logic previously spread across modules.

    Args:
        url (str, optional): URL of the page
        html_content (str, optional): HTML content to analyze
        university_name (str, optional): Name of the university for context

    Returns:
        dict or None: Information about the detected application system(s)
    """
    detected_systems = []

    # Early exit for empty content
    if not html_content and not url and not university_name:
        return None

    # First check if there's a special case for this university
    if university_name:
        # Check special cases for universities (university-specific handling)
        for univ_pattern, special_case in UNIVERSITY_SPECIAL_CASES.items():
            # Simple exact match
            if univ_pattern.lower() == university_name.lower():
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
                        "source": "university_special_case",
                    }

            # Check alternate names
            if "alternate_names" in special_case and university_name:
                if university_name.lower() in [
                    name.lower() for name in special_case.get("alternate_names", [])
                ]:
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
                            "institution_code": special_case.get(
                                "institution_code", ""
                            ),
                            "source": "university_special_case_alternate",
                        }

    # Then check if there's a special case for the domain
    if url:
        # Check domain pattern special cases
        for pattern_info in DOMAIN_PATTERNS:
            if re.search(pattern_info["pattern"], url, re.IGNORECASE):
                system_key = pattern_info.get("system")
                if system_key and system_key in EXTERNAL_APPLICATION_SYSTEMS:
                    return {
                        "system": system_key,
                        "name": EXTERNAL_APPLICATION_SYSTEMS[system_key]["name"],
                        "url": pattern_info.get(
                            "application_portal",
                            EXTERNAL_APPLICATION_SYSTEMS[system_key]["url"],
                        ),
                        "note": pattern_info.get("note", ""),
                        "source": "domain_pattern",
                    }

    # Check HTML content for system references
    if html_content:
        html_lower = html_content.lower()

        # Check for each application system's identifiers
        for system, system_info in EXTERNAL_APPLICATION_SYSTEMS.items():
            # Ensure system_info is a dictionary, not a string
            if not isinstance(system_info, dict):
                continue

            identifiers = system_info.get("identifiers", [])

            # Also use the system name and official name as identifiers
            identifiers.append(system)
            # Ensure "name" exists and is a string before calling lower()
            if "name" in system_info and isinstance(system_info["name"], str):
                identifiers.append(system_info["name"].lower())

            for identifier in identifiers:
                if identifier in html_lower:
                    # Create system result using get_system_url for consistency
                    system_result = get_system_url(system, university_name)
                    system_result["found_reference"] = identifier
                    system_result["source"] = "html_content"

                    # Look for institution codes in HTML
                    inst_code_patterns = [
                        r"institution code:?\s*([A-Z0-9]{4,6})",
                        r"college code:?\s*([A-Z0-9]{4,6})",
                        r"university code:?\s*([A-Z0-9]{4,6})",
                        r"ucas code:?\s*([A-Z0-9]{4,6})",
                    ]

                    for pattern in inst_code_patterns:
                        code_match = re.search(pattern, html_lower)
                        if code_match:
                            system_result["institution_code"] = code_match.group(
                                1
                            ).upper()
                            break

                    detected_systems.append(system_result)
                    break  # Found a match for this system, move to next

        # Return the first detected system if any found
        if detected_systems:
            return detected_systems[0]

    # Check based on university location/region inference
    if university_name and not detected_systems:
        # Simple region inference - could be expanded with more sophisticated logic
        uk_patterns = [
            "university of",
            "king's college",
            "imperial college",
            "oxford",
            "cambridge",
        ]
        us_patterns = ["university of", "state university", "college"]

        if any(pattern in university_name.lower() for pattern in uk_patterns):
            return get_system_url("ucas", university_name)
        elif any(pattern in university_name.lower() for pattern in us_patterns):
            return get_system_url("common_app", university_name)

    # No external system detected
    return None
