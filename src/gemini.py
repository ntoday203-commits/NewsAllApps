"""Use the Gemini API to clean and summarize extracted article text."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.utils import retry

logger = logging.getLogger("news_aggregator.gemini")

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_CONTENT_CHARS = 12000

_PROMPT_TEMPLATE = """You are a careful news editor. Read the article below and
produce a concise, factual summary plus a short list of key points.

Rules:
- Only use information present in the article. Do not invent facts.
- Strip navigation text, ads, and unrelated boilerplate before summarizing.
- Keep the summary to 2-4 sentences.
- Provide 3-5 key points as short standalone statements.

Title: {title}

Article:
{content}

Respond as JSON with this exact shape:
{{"summary": "...", "key_points": ["...", "..."]}}
"""

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
    return _client


@retry(times=3, delay=3, backoff=2, exceptions=(genai_errors.APIError,))
def _generate(prompt: str) -> str:
    client = _get_client()
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text


def summarize_article(title: str, content: str) -> Optional[dict]:
    """Return {"summary": str, "key_points": [str, ...]} or None on failure."""
    if not content:
        return None

    trimmed = content[:MAX_CONTENT_CHARS]
    prompt = _PROMPT_TEMPLATE.format(title=title or "Untitled", content=trimmed)

    try:
        raw = _generate(prompt)
    except genai_errors.APIError as exc:
        logger.error("Gemini API call failed for %r: %s", title, exc)
        return None
    except RuntimeError as exc:
        logger.error("Gemini not configured: %s", exc)
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON output for %r; using raw text as summary", title)
        return {"summary": raw.strip(), "key_points": []}

    return {
        "summary": parsed.get("summary", ""),
        "key_points": parsed.get("key_points", []),
    }
