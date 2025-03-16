"""
AI evaluation of application pages using OpenAI
"""

import asyncio
import re
import time
from datetime import datetime

import openai
from loguru import logger

from analysis.external_system_url_generator import extract_application_system_from_html

from config import Config


# API rate limiting
api_semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_API_CALLS)

# Global tracker for API metrics with lock
api_metrics = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
    "pages_evaluated": 0,
}
api_metrics_lock = asyncio.Lock()


def parse_evaluation_response(result_text):
    """Parse the enhanced AI evaluation response including external system information."""
    result_match = re.search(r"RESULT:\s*(TRUE|FALSE)", result_text, re.IGNORECASE)
    category_match = re.search(r"CATEGORY:\s*([1-4])", result_text, re.IGNORECASE)
    explanation_match = re.search(
        r"EXPLANATION:\s*(.*?)(\n\w+:|$)", result_text, re.DOTALL
    )

    # Extract external systems information
    external_systems_match = re.search(
        r"EXTERNAL_SYSTEMS:\s*(.*?)(\n\w+:|$)", result_text, re.DOTALL
    )
    institution_code_match = re.search(
        r"INSTITUTION_CODE:\s*(.*?)(\n\w+:|$)", result_text, re.DOTALL
    )
    program_code_match = re.search(
        r"PROGRAM_CODE:\s*(.*?)(\n\w+:|$)", result_text, re.DOTALL
    )

    is_actual_application = False
    category = 0
    explanation = "Could not evaluate"

    # External systems information
    external_systems = []
    institution_code = None
    program_code = None

    if result_match:
        is_actual_application = result_match.group(1).upper() == "TRUE"

    if category_match:
        category = int(category_match.group(1))

    if explanation_match:
        explanation = explanation_match.group(1).strip()

    # Extract external systems
    if external_systems_match:
        systems_text = external_systems_match.group(1).strip()
        if systems_text.lower() != "none":
            # Split by commas or other separators
            system_candidates = re.split(r"[,;]|\sand\s", systems_text)
            for system in system_candidates:
                system = system.strip().lower()
                if system and system != "none":
                    # Map to standardized system names
                    if "ucas" in system:
                        external_systems.append("ucas")
                    elif "common app" in system or "commonapp" in system:
                        external_systems.append("common_app")
                    elif "coalition" in system:
                        external_systems.append("coalition")
                    elif "applytexas" in system or "apply texas" in system:
                        external_systems.append("applytexas")
                    elif "calstate" in system or "cal state" in system:
                        external_systems.append("cal_state")
                    elif "ouac" in system:
                        external_systems.append("ouac")
                    elif "uac" in system:
                        external_systems.append("uac")
                    elif "studylink" in system:
                        external_systems.append("studylink")
                    elif "uni-assist" in system or "uniassist" in system:
                        external_systems.append("uni_assist")
                    elif "gradcas" in system or "graduate" in system:
                        external_systems.append("postgrad")

    # Extract codes
    if institution_code_match:
        code_text = institution_code_match.group(1).strip()
        if code_text.lower() != "none":
            institution_code = code_text

    if program_code_match:
        code_text = program_code_match.group(1).strip()
        if code_text.lower() != "none":
            program_code = code_text

    # Create additional metadata about the type of application page
    application_type = "N/A"
    if category == 1:
        application_type = "direct_application"
    elif category == 2:
        application_type = "external_application_reference"
    elif category == 3:
        application_type = "information_only"

    return (
        is_actual_application,
        explanation,
        application_type,
        category,
        external_systems,
        institution_code,
        program_code,
    )


async def evaluate_application_page(app_page):
    """Use GPT-4o-mini to evaluate if a page is truly an application page."""
    global api_metrics, api_metrics_lock

    try:
        # Use semaphore to limit concurrent API calls
        async with api_semaphore:
            system_prompt = """
            You are an expert at analyzing university websites and identifying actual application pages versus informational pages.
            
            Please classify this page into ONE of the following categories:
            1. DIRECT APPLICATION PAGE: Contains actual application form, immediate "Apply Now" buttons, login portal for applicants, or direct links to begin an application
            2. APPLICATION PORTAL REFERENCE: References external application systems (like UCAS, Common App, etc.) with specific instructions on how to use them for this university
            3. INFORMATION ONLY: Contains general information but no specific application instructions or requirements

            Look carefully for:
            - References to external application systems or portals (UCAS, Common App, Coalition App, UC Application, ApplyTexas, Cal State Apply, etc.)
            - Multi-step application instructions or workflows
            - Application deadlines and requirements
            - Specific codes or identifiers needed for applications (institution codes, program codes)
            - Links or references to university-specific application portals or systems
            - Instructions on what happens after submitting an initial application
            - Whether this is for undergraduate or graduate/doctoral programs

            Your task:
            - Respond with TRUE if this is category 1 or 2 (directly useful for applying)
            - Respond with FALSE if this is category 3 (just information)
            - Then provide a brief explanation for your decision and identify which category (1-3) it belongs to
            - If you find any specific external application systems (UCAS, Common App, etc.), institution codes, or program codes, mention them explicitly.
            - Determine if this is for undergraduate, graduate, or doctoral programs.

            Format your response like this:
            RESULT: TRUE/FALSE
            CATEGORY: 1/2/3
            EXPLANATION: Your explanation here
            EXTERNAL_SYSTEMS: List any external systems mentioned (UCAS, Common App, UC Application, etc.) or NONE
            INSTITUTION_CODE: Any institution codes found or NONE
            PROGRAM_CODE: Any program codes found or NONE
            EDUCATION_LEVEL: undergraduate/graduate/doctoral/unknown
            """

            user_prompt = f"""
            Analyze this university webpage and determine if it is an application-related page where students can either apply directly or get critical information needed to apply to the university.
            
            You are given the following information:

            University: {app_page['university']}
            Page Title: {app_page['title']}
            URL: {app_page['url']}
            Detected Reasons: {', '.join(app_page['reasons'])}
            
            Please be extremely precise in identifying if this is for undergraduate applications or graduate/doctoral programs. Specifically look for terms like "undergraduate", "freshmen", "first-year", "transfer" for undergraduate, versus "graduate", "master's", "PhD", "doctoral" for graduate programs.
            
            Also carefully identify any external application systems (like UCAS for UK universities, Common App for US colleges, UC Application for University of California campuses, etc.) that are mentioned or referenced.
            """

            # Use the synchronous API but run it in a separate thread to keep things async
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: openai.chat.completions.create(
                    model=Config.MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                ),
            )

            # Track metrics with async lock to prevent race conditions
            async with api_metrics_lock:
                api_metrics["prompt_tokens"] += response.usage.prompt_tokens
                api_metrics["completion_tokens"] += response.usage.completion_tokens
                api_metrics["total_tokens"] += response.usage.total_tokens
                api_metrics["pages_evaluated"] += 1

                # Calculate cost based on model pricing - adjust rates as needed
                rate_per_1k_input = 0.00015  # Rate for GPT-4o-mini prompt tokens
                rate_per_1k_completion = (
                    0.0006  # Rate for GPT-4o-mini completion tokens
                )
                rate_per_1k_cached_input = (
                    0.000075  # Rate for GPT-4o-mini cached prompt tokens
                )

                page_cost = (
                    (response.usage.prompt_tokens / 1000) * rate_per_1k_input
                    + (response.usage.prompt_tokens_details.cached_tokens / 1000)
                    * rate_per_1k_cached_input
                    + (response.usage.completion_tokens / 1000) * rate_per_1k_completion
                )
                api_metrics["estimated_cost_usd"] += page_cost

            result_text = response.choices[0].message.content.strip()

            # Parse the response with our new function - fixed to capture all return values
            (
                is_actual_application,
                explanation,
                application_type,
                category,
                external_systems,
                institution_code,
                program_code,
            ) = parse_evaluation_response(result_text)

            # Extract external systems from HTML directly
            html_content = app_page.get("html_snippet", "")
            university_name = app_page.get("university", "")

            # Use our new function to get application system URLs
            application_systems = extract_application_system_from_html(
                html_content, app_page["url"], university_name
            )

            # Create evaluated entry
            evaluated_entry = app_page.copy()
            evaluated_entry.pop(
                "html_snippet", None
            )  # Remove HTML snippet to save space
            evaluated_entry["is_actual_application"] = is_actual_application
            evaluated_entry["ai_evaluation"] = explanation
            evaluated_entry["application_type"] = application_type
            evaluated_entry["category"] = category

            # Add the external application systems information
            if application_systems:
                evaluated_entry["external_application_systems"] = application_systems
            else:
                evaluated_entry["external_application_systems"] = []

            # Add additional fields from AI evaluation
            if external_systems:
                evaluated_entry["detected_external_systems"] = external_systems
            if institution_code:
                evaluated_entry["institution_code"] = institution_code
            if program_code:
                evaluated_entry["program_code"] = program_code

            log_prefix = (
                "✅ ACTUAL APPLICATION"
                if is_actual_application
                else "❌ NOT APPLICATION"
            )

            # Log if external systems were found
            if application_systems:
                systems_found = ", ".join(
                    [sys["system_name"] for sys in application_systems]
                )
                logger.info(
                    f"Evaluated {app_page['url']}: {log_prefix} | External Systems: {systems_found}"
                )
            else:
                logger.info(f"Evaluated {app_page['url']}: {log_prefix}")

            return evaluated_entry

    except Exception as e:
        logger.error(f"Error evaluating {app_page['url']}: {e}")

        # Return with error message
        evaluated_entry = app_page.copy()
        evaluated_entry.pop("html_snippet", None)
        evaluated_entry["is_actual_application"] = False
        evaluated_entry["ai_evaluation"] = f"Error during evaluation: {str(e)}"
        evaluated_entry["application_type"] = "error"
        evaluated_entry["category"] = 0
        evaluated_entry["external_application_systems"] = []

        return evaluated_entry


async def evaluate_all_applications(found_applications):
    """Evaluate all found application pages using GPT-4o-mini."""

    if not found_applications:
        logger.warning("No application pages to evaluate")
        return []

    logger.info(
        f"Evaluating {len(found_applications)} application pages with {Config.MODEL_NAME}..."
    )

    # Evaluate in batches to avoid overwhelming the API
    results = []
    batch_size = Config.MAX_EVAL_BATCH

    for i in range(0, len(found_applications), batch_size):
        batch = found_applications[i : i + batch_size]
        logger.info(
            f"Evaluating batch {i//batch_size + 1} of {(len(found_applications)-1)//batch_size + 1} ({len(batch)} pages)"
        )

        # Process the batch concurrently
        batch_results = await asyncio.gather(
            *[evaluate_application_page(app) for app in batch]
        )
        results.extend(batch_results)

        # Brief pause between batches
        if i + batch_size < len(found_applications):
            await asyncio.sleep(1)

    return results


def get_api_metrics():
    """Return a copy of the current API metrics."""
    global api_metrics

    metrics = api_metrics.copy()
    metrics["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metrics["model"] = Config.MODEL_NAME

    return metrics
