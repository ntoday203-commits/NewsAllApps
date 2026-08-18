"""Orchestrate the pipeline for every app: search -> extract -> summarize ->
cache -> write each news_source's current results to its own JSON file."""

from __future__ import annotations

import logging
import os
from typing import Optional

from src import apps_config, article_extractor, gemini, google_news
from src.utils import generate_article_id, load_json, now_iso, save_json

logger = logging.getLogger("news_aggregator.processor")

DATA_DIR = "data"
APPS_INDEX_PATH = os.path.join("config", "apps.json")
APPS_DIR = os.path.join("config", "apps")
CACHE_PATH = os.path.join(DATA_DIR, "processed_cache.json")


def _load_cache() -> dict:
    return load_json(CACHE_PATH, default={})


def _save_cache(cache: dict) -> None:
    save_json(CACHE_PATH, cache)


def _build_record(item, extracted: Optional[dict], gemini_result: Optional[dict], source: dict, app_name: str) -> dict:
    extracted = extracted or {}
    article_url = extracted.get("article_url") or item.google_news_url
    return {
        "id": generate_article_id(article_url),
        "title": extracted.get("title") or item.title,
        "source": extracted.get("publisher") or item.source,
        "author": extracted.get("author"),
        "published_at": extracted.get("published_at") or item.published_at,
        "image": extracted.get("image"),
        "url": article_url,
        "google_news_url": item.google_news_url,
        "content": extracted.get("content"),
        "summary": (gemini_result or {}).get("summary", ""),
        "key_points": (gemini_result or {}).get("key_points", []),
        "language": source.get("language", "en"),
        "country": source.get("country", "US"),
        "topic": source.get("topic") or source.get("location") or source.get("function"),
        "app": app_name,
        "collected_at": now_iso(),
    }


def _process_one_new_article(item, existing_ids: set, archive_ids: set, source: dict, app_name: str, cache: dict) -> Optional[dict]:
    """Resolve, extract, and summarize a single Google News item. Returns the
    finished record, or None if it turns out to already be saved elsewhere."""
    cached = cache.get(generate_article_id(item.google_news_url))
    if cached:
        if cached["id"] in existing_ids or cached["id"] in archive_ids:
            return None
        logger.info("Using cached article (already processed for another source)")
        return cached

    logger.info("Resolving article URL...")
    article_url = google_news.resolve_article_url(item.google_news_url)

    logger.info("Extracting article...")
    extracted = article_extractor.extract_article(article_url)
    if extracted:
        logger.info("Article extracted successfully")
    else:
        logger.warning("Extraction failed, keeping Google News metadata only")

    final_id = generate_article_id((extracted or {}).get("article_url") or article_url)
    if final_id in existing_ids or final_id in archive_ids:
        return None
    if final_id in cache:
        logger.info("Using cached article (already processed under resolved URL)")
        return cache[final_id]

    content = (extracted or {}).get("content")
    gemini_result = None
    if content:
        logger.info("Generating Gemini summary...")
        gemini_result = gemini.summarize_article(extracted.get("title") or item.title, content)
        if gemini_result:
            logger.info("Summary generated")

    record = _build_record(item, extracted, gemini_result, source, app_name)
    record["id"] = final_id
    return record


def _process_source(app_name: str, source: dict, cache: dict) -> None:
    search_cfg = apps_config.source_to_search_config(source, app_name)
    label = search_cfg["name"]
    cap = source.get("max_results", 99)
    filename = source["filename"]

    output_path = os.path.join(DATA_DIR, app_name, filename)
    archive_path = os.path.join(DATA_DIR, app_name, "archive", filename)
    existing = load_json(output_path, default=[])
    archive = load_json(archive_path, default=[])
    existing_ids = {r["id"] for r in existing}
    archive_ids = {r["id"] for r in archive}

    logger.info("Starting Google News search: %s", label)
    items = google_news.search(search_cfg)
    logger.info("Found %d articles for %s", len(items), label)

    saved = False
    for i, item in enumerate(items, 1):
        candidate_id = generate_article_id(item.google_news_url)
        if candidate_id in existing_ids or candidate_id in archive_ids:
            continue

        logger.info("Processing article %d/%d: %s", i, len(items), item.title)
        try:
            record = _process_one_new_article(item, existing_ids, archive_ids, source, app_name, cache)
        except Exception as exc:  # noqa: BLE001 - a single bad article must not stop the run
            logger.error("Failed to process article %r: %s", item.title, exc)
            continue

        if record is None:
            continue

        cache[generate_article_id(item.google_news_url)] = record
        cache[record["id"]] = record
        existing.insert(0, record)
        existing_ids.add(record["id"])
        logger.info("Article saved: %s", record["title"])
        saved = True
        break

    if not saved:
        logger.info("No new articles for %s", label)

    if len(existing) > cap:
        overflow = existing[cap:]
        existing = existing[:cap]
        archive = overflow + archive
        save_json(archive_path, archive)
        logger.info("Archived %d article(s) for %s (cap %d)", len(overflow), label, cap)

    save_json(output_path, existing)
    logger.info("%s now has %d article(s)", output_path, len(existing))


def run_pipeline(apps_index_path: str = APPS_INDEX_PATH, apps_dir: str = APPS_DIR) -> None:
    apps = apps_config.load_apps(apps_index_path, apps_dir)
    if not apps:
        logger.warning("No apps to process")
        return

    cache = _load_cache()

    for app_cfg in apps:
        app_name = app_cfg["app_name"]
        logger.info("Processing app: %s", app_name)

        for source in app_cfg.get("news_sources", []):
            filename = source.get("filename")
            if not filename:
                logger.error("Skipping source without filename in app %s: %s", app_name, source)
                continue

            try:
                _process_source(app_name, source, cache)
            except ValueError as exc:
                logger.error("Skipping source %s in app %s: %s", filename, app_name, exc)
                continue
            except Exception as exc:  # noqa: BLE001 - one bad source must not stop the run
                logger.error("Source %s in app %s failed entirely: %s", filename, app_name, exc)
                continue

    _save_cache(cache)
    logger.info("Pipeline complete")
