"""Load the multi-app configuration: an index of app config files, each
listing the Google News sources that make up that app's feeds."""

from __future__ import annotations

import logging
import os

from src.utils import load_json

logger = logging.getLogger("news_aggregator.apps_config")

# Maps a news_source "function" to how it should query Google News.
SUPPORTED_FUNCTIONS = {"get_top_news", "get_news_by_topic", "get_local_news"}

# How many feed entries to scan per run looking for one new article. Kept
# generous and decoupled from max_results (the live-file cap) so a small cap
# doesn't stop the pipeline from ever seeing fresh items further down the feed.
MIN_SCAN_WINDOW = 50

# Applied to every topic/location entry — not configurable per app config.
DEFAULT_COUNTRY = "GB"
DEFAULT_LANGUAGE = "en"
DEFAULT_MAX_RESULTS = 99


def _entries_to_sources(entries: list[dict], function: str, field: str) -> list[dict]:
    sources = []
    for entry in entries:
        sources.append({
            "function": function,
            field: entry.get("topic"),
            "filename": entry.get("filename"),
            "country": DEFAULT_COUNTRY,
            "language": DEFAULT_LANGUAGE,
            "max_results": DEFAULT_MAX_RESULTS,
        })
    return sources


def load_apps(index_path: str, apps_dir: str) -> list[dict]:
    """Read the apps index (list of config filenames) and load each app's
    config. Missing or invalid app files are logged and skipped."""
    index = load_json(index_path, default={})
    app_files = index.get("apps", [])
    if not app_files:
        logger.warning("No apps listed in %s", index_path)
        return []

    apps = []
    for filename in app_files:
        path = os.path.join(apps_dir, filename)
        app_cfg = load_json(path, default=None)
        if app_cfg is None:
            logger.error("Could not load app config %s", path)
            continue
        if not app_cfg.get("app_name"):
            logger.error("App config %s is missing app_name", path)
            continue

        news_sources = _entries_to_sources(app_cfg.get("topics", []), "get_news_by_topic", "topic")
        news_sources += _entries_to_sources(app_cfg.get("locations", []), "get_local_news", "location")
        if not news_sources:
            logger.error("App config %s has no topics or locations", path)
            continue

        app_cfg["news_sources"] = news_sources
        apps.append(app_cfg)
    return apps


def source_to_search_config(source: dict, app_name: str) -> dict:
    """Translate a news_source entry into the internal search config that
    src.google_news.search() understands."""
    function = source.get("function")
    if function not in SUPPORTED_FUNCTIONS:
        raise ValueError(f"Unsupported function {function!r} (supported: {sorted(SUPPORTED_FUNCTIONS)})")

    search_config = {
        "name": f"{app_name}/{source.get('filename', function)}",
        "country": source.get("country", "US"),
        "language": source.get("language", "en"),
        "num_articles": max(source.get("max_results", 10), MIN_SCAN_WINDOW),
    }

    if function == "get_top_news":
        search_config["mode"] = "top"
    elif function == "get_news_by_topic":
        if not source.get("topic"):
            raise ValueError("get_news_by_topic requires a 'topic' field")
        search_config["topic"] = source["topic"]
    elif function == "get_local_news":
        if not source.get("location"):
            raise ValueError("get_local_news requires a 'location' field")
        search_config["location"] = source["location"]

    return search_config
