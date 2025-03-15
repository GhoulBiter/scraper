"""
Static URL generator for external application systems
"""

from analysis.page_analyzer import EXTERNAL_APPLICATION_SYSTEMS

# Comprehensive dictionary of common application systems with their base URLs
# and additional information about how to use them
APPLICATION_SYSTEM_INFO = {
    "ucas": {
        "name": "UCAS (UK Universities and Colleges Admissions Service)",
        "base_url": "https://www.ucas.com/apply",
        "search_url": "https://digital.ucas.com/search",
        "description": "The central application service for UK undergraduate programs",
        "institution_code_format": "Four-character code (e.g., 'CAMB' for Cambridge)",
        "application_steps": [
            "Create a UCAS account",
            "Complete personal details",
            "Add course choices (up to 5)",
            "Write personal statement",
            "Get reference",
            "Pay application fee and submit",
        ],
    },
    "common_app": {
        "name": "Common Application",
        "base_url": "https://apply.commonapp.org/login",
        "search_url": "https://apply.commonapp.org/search",
        "description": "Application platform for over 900 colleges and universities, primarily in the US",
        "application_steps": [
            "Create Common App account",
            "Add colleges to your list",
            "Complete the common application form",
            "Answer college-specific questions",
            "Submit application for each college",
            "Pay application fees for each college",
        ],
    },
    "coalition": {
        "name": "Coalition Application",
        "base_url": "https://app.coalitionforcollegeaccess.org/",
        "search_url": "https://app.coalitionforcollegeaccess.org/search",
        "description": "Alternative to Common App, used by about 150 US colleges and universities",
        "application_steps": [
            "Create Coalition account",
            "Build profile",
            "Add colleges to your list",
            "Answer university-specific questions",
            "Submit your application",
        ],
    },
    "applytexas": {
        "name": "ApplyTexas",
        "base_url": "https://www.applytexas.org/adappc/gen/c_start.WBX",
        "description": "Application system for Texas public universities and community colleges",
        "application_steps": [
            "Create ApplyTexas account",
            "Select target universities",
            "Complete biographical information",
            "Complete educational background",
            "Complete residency information",
            "Submit application",
        ],
    },
    "cal_state": {
        "name": "Cal State Apply",
        "base_url": "https://www.calstate.edu/apply",
        "description": "Application portal for all California State University campuses",
        "application_steps": [
            "Create Cal State Apply account",
            "Select campuses and programs",
            "Complete four quadrants: Personal Information, Academic History, Supporting Information, and Program Materials",
            "Submit application and pay fee",
        ],
    },
    "uc_app": {
        "name": "University of California Application",
        "base_url": "https://apply.universityofcalifornia.edu/my-application/",
        "description": "Application system for all University of California campuses",
        "application_steps": [
            "Create UC application account",
            "Complete personal information",
            "Add academic history",
            "Complete personal insight questions",
            "Review and submit application",
        ],
    },
    "ouac": {
        "name": "Ontario Universities' Application Centre",
        "base_url": "https://www.ouac.on.ca/apply/",
        "description": "Central application service for universities in Ontario, Canada",
        "application_types": {
            "101": "Current Ontario high school students",
            "105": "All other applicants",
        },
        "application_steps": [
            "Select appropriate application type (101 or 105)",
            "Create OUAC account",
            "Complete personal information",
            "Select universities and programs",
            "Submit application and pay fees",
        ],
    },
    "uac": {
        "name": "Universities Admissions Centre (Australia)",
        "base_url": "https://www5.uac.edu.au/uacug/",
        "description": "Central admissions for undergraduate study at participating institutions in NSW and ACT, Australia",
        "application_steps": [
            "Create UAC account",
            "Select courses in order of preference",
            "Provide personal information",
            "Upload supporting documents",
            "Pay application fee",
        ],
    },
    "studylink": {
        "name": "StudyLink (New Zealand)",
        "base_url": "https://www.studylink.govt.nz/apply/",
        "description": "New Zealand's student loan and allowance application system",
        "application_steps": [
            "Create StudyLink account",
            "Complete application for student loan/allowance",
            "Upload supporting documents",
            "Track application status",
        ],
    },
    "uni_assist": {
        "name": "uni-assist (Germany)",
        "base_url": "https://www.uni-assist.de/en/how-to-apply/",
        "description": "Application service for international students applying to German universities",
        "application_steps": [
            "Create uni-assist account",
            "Select universities and programs",
            "Upload required documents",
            "Pay handling fee",
            "Track application status",
        ],
    },
    "postgrad_uk": {
        "name": "UK Postgraduate Application",
        "base_url": "https://www.FindAMasters.com/apply/",
        "description": "Portal for UK postgraduate degree applications",
        "application_steps": [
            "Search for programs",
            "Apply directly through university website",
            "Complete application form",
            "Provide references",
            "Submit research proposal (if applicable)",
        ],
    },
    "graduate_us": {
        "name": "US Graduate School Application",
        "description": "Most US graduate programs require direct application through their websites",
        "common_requirements": [
            "Transcripts",
            "GRE/GMAT scores (if required)",
            "Statement of purpose",
            "Letters of recommendation",
            "CV/Resume",
            "Application fee",
        ],
    },
    "cas": {
        "name": "Centralized Application Service",
        "description": "Field-specific application services in the US",
        "types": {
            "AMCAS": "Medical School (MD) - https://students-residents.aamc.org/applying-medical-school-amcas/applying-medical-school-amcas",
            "PTCAS": "Physical Therapy - https://ptcasdirectory.apta.org/",
            "CASPA": "Physician Assistant - https://caspa.liaisoncas.com/",
            "VMCAS": "Veterinary Medicine - https://www.aavmc.org/becoming-a-veterinarian/how-to-apply/",
            "LSAC": "Law School - https://www.lsac.org/",
            "SOPHAS": "Public Health - https://sophas.org/",
        },
    },
}


def get_application_system_url(system_name, institution_name=None):
    """
    Get pre-generated information about an application system including URLs

    Args:
        system_name (str): The name of the application system
        institution_name (str, optional): Institution name for more specific information

    Returns:
        dict: Information about the application system
    """
    # Normalize system name
    system_name = system_name.lower().replace(" ", "_").replace("-", "_")

    # Look for exact matches first
    if system_name in APPLICATION_SYSTEM_INFO:
        result = APPLICATION_SYSTEM_INFO[system_name].copy()

        # Add institution-specific search if provided
        if institution_name and "search_url" in result:
            search_param = institution_name.lower().replace(" ", "+")
            result["institution_search_url"] = (
                f"{result['search_url']}?q={search_param}"
            )

        return result

    # Handle aliases and partial matches
    system_aliases = {
        "ucas": ["ucas", "uk", "uk_application", "uk_undergrad"],
        "common_app": ["common", "commonapp", "common_application"],
        "coalition": ["coalition_app", "mycoalition"],
        "applytexas": ["texas", "apply_texas"],
        "cal_state": ["csu", "calstate", "california_state"],
        "uc_app": ["uc", "university_of_california", "uc_application"],
        "ouac": ["ontario", "ontario_application"],
        "uac": ["australia", "australian", "nsw"],
        "uni_assist": ["germany", "german", "uniassist"],
        "cas": ["centralized", "centralized_application", "specialized_application"],
    }

    # Check aliases
    for system, aliases in system_aliases.items():
        if system_name in aliases:
            result = APPLICATION_SYSTEM_INFO[system].copy()

            # Add institution-specific search if provided
            if institution_name and "search_url" in result:
                search_param = institution_name.lower().replace(" ", "+")
                result["institution_search_url"] = (
                    f"{result['search_url']}?q={search_param}"
                )

            return result

    # Return a general guide if no specific system is found
    return {
        "name": "General Application Guide",
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


def detect_application_systems(html_content, url=""):
    """
    Detect external application systems mentioned in HTML content

    Args:
        html_content (str): HTML content to analyze
        url (str, optional): URL of the page for additional context

    Returns:
        list: List of detected application systems
    """

    detected_systems = []

    # Bail out on empty content
    if not html_content:
        return detected_systems

    # Convert to lowercase for easier matching
    html_lower = html_content.lower()

    # Check for each application system
    for system, identifiers in EXTERNAL_APPLICATION_SYSTEMS.items():
        for identifier in identifiers:
            if identifier in html_lower:
                if system not in detected_systems:
                    detected_systems.append(system)
                break

    # Add some additional checks for systems not in the original list
    additional_systems = [
        ("uc_app", ["uc application", "university of california application"]),
        ("postgrad_uk", ["uk postgraduate", "uk masters", "uk phd"]),
        ("graduate_us", ["us graduate", "us grad school"]),
        ("cas", ["amcas", "ptcas", "caspa", "vmcas", "lsac", "sophas"]),
    ]

    for system, identifiers in additional_systems:
        for identifier in identifiers:
            if identifier in html_lower:
                if system not in detected_systems:
                    detected_systems.append(system)
                break

    return detected_systems


def generate_application_urls_report(detected_systems, institution_name=None):
    """
    Generate a comprehensive report with URLs for detected application systems

    Args:
        detected_systems (list): List of detected system names
        institution_name (str, optional): Name of the institution

    Returns:
        dict: Dictionary with detailed application information
    """
    report = {
        "detected_systems": [],
        "application_urls": {},
        "general_guidance": "Always check the official university website for the most up-to-date application information.",
    }

    if not detected_systems:
        report["detected_systems"] = ["No specific application systems detected"]
        return report

    # Process each detected system
    for system in detected_systems:
        system_info = get_application_system_url(system, institution_name)

        # Add to detected systems list
        report["detected_systems"].append(system_info["name"])

        # Add detailed information to application_urls
        report["application_urls"][system] = {
            "name": system_info["name"],
            "base_url": system_info.get(
                "base_url", "Direct application through institution"
            ),
            "description": system_info["description"],
        }

        # Add application steps if available
        if "application_steps" in system_info:
            report["application_urls"][system]["application_steps"] = system_info[
                "application_steps"
            ]

        # Add institution-specific search URL if available
        if "institution_search_url" in system_info:
            report["application_urls"][system]["institution_search_url"] = system_info[
                "institution_search_url"
            ]

        # Add any other system-specific information
        if "institution_code_format" in system_info:
            report["application_urls"][system]["institution_code_format"] = system_info[
                "institution_code_format"
            ]

        if "application_types" in system_info:
            report["application_urls"][system]["application_types"] = system_info[
                "application_types"
            ]

        if "types" in system_info:
            report["application_urls"][system]["subtypes"] = system_info["types"]

        if "common_requirements" in system_info:
            report["application_urls"][system]["common_requirements"] = system_info[
                "common_requirements"
            ]

    return report
