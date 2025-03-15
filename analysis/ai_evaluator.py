"""
AI evaluation of application pages using OpenAI
"""

import asyncio
import re
import time
from datetime import datetime

import openai
from loguru import logger

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


async def evaluate_application_page(app_page):
    """Use GPT-4o-mini to evaluate if a page is truly an application page."""
    global api_metrics, api_metrics_lock

    try:
        # Use semaphore to limit concurrent API calls
        async with api_semaphore:
            prompt = f"""
            Analyze this university webpage and determine if it is an actual application page or portal where students can apply to the university.

            University: {app_page['university']}
            Page Title: {app_page['title']}
            URL: {app_page['url']}
            Detected Reasons: {', '.join(app_page['reasons'])}

            Please determine:
            1. Is this a direct application page or portal where students can start/submit an application?
            2. Is this a page with information about how to apply but not an actual application?
            3. Is this an unrelated page that was incorrectly flagged?

            Focus on whether students can actually BEGIN or SUBMIT an application on this page.
            Look for forms, "Apply Now" buttons that lead directly to applications, links or buttons to outside domains and services (Common App in the US, UCAS in the UK, UniAssist in Germany, etc.), login portals specifically for applicants, etc.

            Your task:
            - Respond with TRUE if this is definitely an actual application page or portal where students can apply
            - Respond with FALSE if this is just information or unrelated
            - Then provide a brief explanation for your decision
            
            Format your response like this:
            RESULT: TRUE/FALSE
            EXPLANATION: Your explanation here
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
                            "content": "You are an expert at analyzing university websites and identifying actual application pages versus informational pages.",
                        },
                        {"role": "user", "content": prompt},
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

            # Parse the response
            result_match = re.search(
                r"RESULT:\s*(TRUE|FALSE)", result_text, re.IGNORECASE
            )
            explanation_match = re.search(
                r"EXPLANATION:\s*(.*)", result_text, re.DOTALL
            )

            is_actual_application = False
            explanation = "Could not evaluate"

            if result_match:
                is_actual_application = result_match.group(1).upper() == "TRUE"

            if explanation_match:
                explanation = explanation_match.group(1).strip()

            # Create evaluated entry
            evaluated_entry = app_page.copy()
            evaluated_entry.pop(
                "html_snippet", None
            )  # Remove HTML snippet to save space
            evaluated_entry["is_actual_application"] = is_actual_application
            evaluated_entry["ai_evaluation"] = explanation

            log_prefix = (
                "✅ ACTUAL APPLICATION"
                if is_actual_application
                else "❌ NOT APPLICATION"
            )
            logger.info(f"Evaluated {app_page['url']}: {log_prefix}")

            return evaluated_entry

    except Exception as e:
        logger.error(f"Error evaluating {app_page['url']}: {e}")

        # Return with error message
        evaluated_entry = app_page.copy()
        evaluated_entry.pop("html_snippet", None)
        evaluated_entry["is_actual_application"] = False
        evaluated_entry["ai_evaluation"] = f"Error during evaluation: {str(e)}"

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
