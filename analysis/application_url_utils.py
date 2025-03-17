"""
Utility module for easily retrieving application system URLs
"""

from models.application_systems import get_system_url


def get_urls_for_university(university_name, systems=None):
    """
    Get application URLs for a specific university across multiple systems

    Args:
        university_name (str): The name of the university
        systems (list, optional): List of systems to check, or None for all common systems

    Returns:
        dict: Dictionary of application URLs keyed by system name
    """
    # Default to common systems if none provided
    if not systems:
        systems = [
            "ucas",
            "common_app",
            "coalition",
            "applytexas",
            "cal_state",
            "uc_app",
            "ouac",
            "uac",
            "uni_assist",
        ]

    results = {}

    for system in systems:
        system_info = get_system_url(system, university_name)

        # Only include systems with a base URL
        if "base_url" in system_info:
            results[system] = {
                "name": system_info["name"],
                "base_url": system_info["base_url"],
            }

            # Add search URL if available
            if "institution_search_url" in system_info:
                results[system]["search_url"] = system_info["institution_search_url"]

    return results


def get_system_url_by_region(university_name, region):
    """
    Get the most appropriate application system URL based on geographic region

    Args:
        university_name (str): The name of the university
        region (str): Geographic region (e.g., "UK", "US", "Australia", "Canada", "Germany")

    Returns:
        dict: Information about the most relevant application system
    """
    # Map regions to application systems
    region_map = {
        "uk": "ucas",
        "united kingdom": "ucas",
        "england": "ucas",
        "scotland": "ucas",
        "wales": "ucas",
        "northern ireland": "ucas",
        "us": "common_app",
        "usa": "common_app",
        "united states": "common_app",
        "australia": "uac",
        "nsw": "uac",
        "act": "uac",
        "canada": "ouac",
        "ontario": "ouac",
        "germany": "uni_assist",
        "deutschland": "uni_assist",
        "texas": "applytexas",
        "tx": "applytexas",
        "california": "cal_state",
        "ca": "cal_state",
        "new zealand": "studylink",
        "nz": "studylink",
    }

    # Normalize region
    normalized_region = region.lower().strip()

    # Get the appropriate system
    system = region_map.get(
        normalized_region, "common_app"
    )  # Default to Common App if region unknown

    # Get and return the system URL
    return get_system_url(system, university_name)


def lookup_institution_code(university_name, system="ucas"):
    """
    Lookup institution codes for universities in specific application systems

    This is a simple mock implementation with a few example codes.
    In a real implementation, this would connect to a database of institution codes.

    Args:
        university_name (str): The name of the university
        system (str): The application system to check

    Returns:
        str: Institution code if found, otherwise None
    """
    # Normalize university name
    univ_name = university_name.lower().strip()

    # Mock database of institution codes
    ucas_codes = {
        "university of cambridge": "CAM",
        "university of oxford": "OXFD",
        "imperial college london": "IMP",
        "university college london": "UCL",
        "london school of economics": "LSE",
        "university of edinburgh": "EDINB",
        "king's college london": "KCL",
        "university of manchester": "MANU",
    }

    common_app_codes = {
        "harvard university": "4154",
        "stanford university": "4704",
        "massachusetts institute of technology": "3514",
        "yale university": "3987",
        "princeton university": "2672",
        "columbia university": "2116",
        "university of pennsylvania": "3731",
        "california institute of technology": "4034",
    }

    # Select appropriate code database
    if system.lower() == "ucas":
        return ucas_codes.get(univ_name)
    elif system.lower() in ["common_app", "common", "commonapp"]:
        return common_app_codes.get(univ_name)
    else:
        return None


def print_application_guidance(university_name, system=None):
    """
    Print user-friendly guidance for applying to a university

    Args:
        university_name (str): The name of the university
        system (str, optional): Specific application system to use

    Returns:
        str: Formatted guidance text
    """
    if system:
        # Get specific system info
        system_info = get_system_url(system, university_name)

        # Build guidance text
        guidance = f"APPLICATION GUIDANCE FOR {university_name.upper()} VIA {system_info['name'].upper()}\n\n"
        guidance += f"Application Website: {system_info.get('base_url', 'Check university website')}\n\n"

        if "institution_search_url" in system_info:
            guidance += (
                f"University Search URL: {system_info['institution_search_url']}\n\n"
            )

        guidance += f"Description: {system_info['description']}\n\n"

        if "application_steps" in system_info:
            guidance += "Application Steps:\n"
            for i, step in enumerate(system_info["application_steps"], 1):
                guidance += f"{i}. {step}\n"

        # Add institution code if available
        inst_code = lookup_institution_code(university_name, system)
        if inst_code:
            guidance += f"\nInstitution Code: {inst_code}\n"

        return guidance
    else:
        # Get URLs for multiple systems
        urls = get_urls_for_university(university_name)

        # Build guidance text
        guidance = f"APPLICATION OPTIONS FOR {university_name.upper()}\n\n"
        guidance += f"The following application systems may be available for {university_name}:\n\n"

        for system, info in urls.items():
            guidance += f"- {info['name']}: {info['base_url']}\n"
            if "search_url" in info:
                guidance += f"  Search URL: {info['search_url']}\n"

        guidance += "\nPlease check the university's official website to confirm which application system to use."

        return guidance
