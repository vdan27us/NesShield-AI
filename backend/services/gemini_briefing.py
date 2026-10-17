
import json
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


def generate_financial_briefing(financial_data: dict) -> str:
    """Explain supplied financial calculations without inventing metrics."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the project's .env file."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are the financial-risk analyst inside Nesshield AI, a cash-flow
monitoring prototype for small businesses.

Analyze ONLY the supplied data. Do not invent numbers, transactions,
probabilities, or facts. Python has already calculated the metrics;
your job is to explain them clearly.

Return a concise briefing using these headings:

## Executive summary
Two or three sentences describing the current liquidity outlook.

## Key risk drivers
List up to three specific drivers supported by the data. Distinguish
a safety-buffer breach from an actual negative balance.

## Recommended actions
Give up to three practical, cautious actions a business owner could
consider. Clearly label these as suggestions, not guarantees.

## Important limitations
Explain that Nessie is a sandbox, the Monte Carlo results depend on
assumptions, and any ML score trained on synthetic data is not a
calibrated real-world probability.

Use plain language. Be specific, not alarmist. If a value is missing,
say it is unavailable instead of guessing. Do not claim to be a
licensed financial adviser.

FINANCIAL DATA:
{json.dumps(financial_data, indent=2, default=str)}
"""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
    )

    text = response.text
    if not text or not text.strip():
        raise RuntimeError("Gemini returned an empty briefing.")

    return text.strip()
