"""Fetch a resolved article URL and extract its title, metadata, and full text."""

from __future__ import annotations

import json
import logging
from typing import Optional

import requests
import trafilatura

from src.utils import normalize_date, retry

logger = logging.getLogger("news_aggregator.article_extractor")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20


@retry(times=2, delay=2, exceptions=(requests.RequestException,))
def _fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_article(url: str) -> Optional[dict]:
    """Download and extract a full article. Returns None on failure so the
    caller can fall back to whatever Google News metadata it already has."""
    try:
        html = _fetch_html(url)
    except requests.RequestException as exc:
        logger.warning("Failed to fetch article HTML for %s: %s", url, exc)
        return None

    extracted_json = trafilatura.extract(
        html,
        url=url,
        output_format="json",
        with_metadata=True,
        include_images=True,
        favor_precision=True,
    )
    if not extracted_json:
        logger.warning("trafilatura could not extract content from %s", url)
        return None

    try:
        data = json.loads(extracted_json)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse extracted content for %s: %s", url, exc)
        return None

    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "author": data.get("author"),
        "publisher": data.get("sitename"),
        "published_at": normalize_date(data.get("date")),
        "image": data.get("image"),
        "content": data.get("text"),
        "article_url": data.get("url") or url,
    }
