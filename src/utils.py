"""Shared helpers: logging, retries, JSON I/O, and URL/id normalization."""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

logger = logging.getLogger("news_aggregator")

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"fbclid", "gclid", "ref", "ref_src", "ncid", "cmpid"}


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once with a simple, readable format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def retry(times: int = 3, delay: float = 2.0, backoff: float = 2.0, exceptions=(Exception,)):
    """Retry a function on failure with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == times:
                        break
                    logger.warning(
                        "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        func.__name__, attempt, times, exc, current_delay,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc

        return wrapper

    return decorator


def canonicalize_url(url: str) -> str:
    """Normalize a URL for stable deduplication: lowercase host, strip
    tracking params, drop fragment, drop trailing slash."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or ""
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
        and not k.lower().startswith(_TRACKING_PARAM_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def generate_article_id(url: str) -> str:
    """Deterministic id derived from the canonical article URL."""
    canonical = canonicalize_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_date(raw: str | None) -> str | None:
    """Parse a loosely-formatted date string (RSS pubDate, article metadata,
    etc.) into ISO 8601, or return None if it can't be parsed."""
    if not raw:
        return None
    from dateutil import parser as date_parser

    try:
        return date_parser.parse(raw).isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read JSON from %s: %s", path, exc)
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
