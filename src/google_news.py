"""Search Google News (via its public RSS feeds) by query, topic, or topic URL."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlparse

import feedparser
import requests
from googlenewsdecoder import gnewsdecoder

from src.utils import normalize_date, retry

logger = logging.getLogger("news_aggregator.google_news")

RSS_BASE = "https://news.google.com/rss"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15

# Fixed section codes Google News exposes as named topics (no per-user id needed).
NAMED_TOPICS = {
    "world", "nation", "business", "technology",
    "entertainment", "sports", "science", "health",
}


@dataclass
class NewsItem:
    title: str
    google_news_url: str
    source: Optional[str]
    published_at: Optional[str]
    description: Optional[str]


def _ceid(country: str, language: str) -> str:
    return f"hl={language}-{country}&gl={country}&ceid={country}:{language}"


def _extract_topic_id(topic_url: str) -> Optional[str]:
    """Pull the opaque topic id out of a full news.google.com/topics/... URL."""
    path = urlparse(topic_url).path
    match = re.search(r"/topics/([^/?]+)", path)
    return match.group(1) if match else None


def build_feed_url(search: dict) -> str:
    """Build the RSS feed URL for a search config entry."""
    country = search.get("country", "US")
    language = search.get("language", "en")
    ceid = _ceid(country, language)

    if search.get("mode") == "top":
        return f"{RSS_BASE}?{ceid}"

    if search.get("location"):
        location = quote(search["location"])
        return f"{RSS_BASE}/headlines/section/geo/{location}?{ceid}"

    if search.get("topic_url"):
        topic_id = _extract_topic_id(search["topic_url"])
        if not topic_id:
            raise ValueError(f"Could not parse topic id from {search['topic_url']!r}")
        return f"{RSS_BASE}/topics/{topic_id}?{ceid}"

    if search.get("topic"):
        topic = search["topic"].strip().upper()
        if topic.lower() in NAMED_TOPICS:
            return f"{RSS_BASE}/headlines/section/topic/{topic}?{ceid}"
        # Not a known named section: treat it as an opaque topic id.
        return f"{RSS_BASE}/topics/{topic}?{ceid}"

    if search.get("query"):
        query = quote(search["query"])
        return f"{RSS_BASE}/search?q={query}&{ceid}"

    raise ValueError("Search config must include one of: mode='top', location, query, topic, topic_url")


@retry(times=3, delay=2, exceptions=(requests.RequestException,))
def _fetch(url: str) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.content


def search(search_config: dict) -> list[NewsItem]:
    """Run a Google News RSS search and return parsed items."""
    feed_url = build_feed_url(search_config)
    limit = search_config.get("num_articles", 10)

    try:
        raw = _fetch(feed_url)
    except requests.RequestException as exc:
        logger.error("Google News request failed for %r: %s", search_config.get("name"), exc)
        return []

    feed = feedparser.parse(raw)
    items = []
    for entry in feed.entries[:limit]:
        source = getattr(entry, "source", None)
        source_title = getattr(source, "title", None) if source else None
        items.append(
            NewsItem(
                title=getattr(entry, "title", "").strip(),
                google_news_url=getattr(entry, "link", ""),
                source=source_title,
                published_at=normalize_date(getattr(entry, "published", None)),
                description=getattr(entry, "summary", None),
            )
        )
    return items


def resolve_article_url(google_news_url: str) -> str:
    """Best-effort resolution of the real publisher URL behind a Google News
    RSS redirect link. Falls back to the original URL if resolution fails."""
    if not google_news_url:
        return google_news_url
    try:
        result = gnewsdecoder(google_news_url, interval=1)
    except Exception as exc:  # noqa: BLE001 - third-party decoder, keep pipeline alive
        logger.warning("Could not resolve article URL for %s: %s", google_news_url, exc)
        return google_news_url

    if result.get("status") and result.get("decoded_url"):
        return result["decoded_url"]

    logger.warning(
        "Could not resolve article URL for %s: %s",
        google_news_url, result.get("message", "unknown error"),
    )
    return google_news_url
