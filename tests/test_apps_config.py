import json
import os
import tempfile
import unittest

from src.apps_config import DEFAULT_COUNTRY, DEFAULT_LANGUAGE, DEFAULT_MAX_RESULTS, load_apps, source_to_search_config
from src.google_news import build_feed_url


class TestSourceToSearchConfig(unittest.TestCase):
    def test_get_top_news(self):
        source = {"function": "get_top_news", "country": "US", "language": "en", "max_results": 50, "filename": "top.json"}
        cfg = source_to_search_config(source, "usanews")
        self.assertEqual(cfg["mode"], "top")
        self.assertEqual(cfg["num_articles"], 50)
        self.assertIn("usanews", cfg["name"])
        self.assertIn("top.json", cfg["name"])

    def test_scan_window_floor_applies_below_50(self):
        source = {"function": "get_top_news", "country": "US", "language": "en", "max_results": 3, "filename": "top.json"}
        cfg = source_to_search_config(source, "usanews")
        self.assertEqual(cfg["num_articles"], 50)

    def test_get_news_by_topic(self):
        source = {"function": "get_news_by_topic", "topic": "WORLD", "country": "US", "language": "en", "filename": "world.json"}
        cfg = source_to_search_config(source, "usanews")
        self.assertEqual(cfg["topic"], "WORLD")
        self.assertNotIn("mode", cfg)

    def test_get_news_by_topic_requires_topic(self):
        source = {"function": "get_news_by_topic", "country": "US", "language": "en", "filename": "x.json"}
        with self.assertRaises(ValueError):
            source_to_search_config(source, "usanews")

    def test_unsupported_function_raises(self):
        source = {"function": "get_news_by_query", "query": "x", "filename": "x.json"}
        with self.assertRaises(ValueError):
            source_to_search_config(source, "usanews")

    def test_get_local_news(self):
        source = {"function": "get_local_news", "location": "London", "country": "GB", "language": "en", "filename": "local.json"}
        cfg = source_to_search_config(source, "uknews")
        self.assertEqual(cfg["location"], "London")

    def test_get_local_news_requires_location(self):
        source = {"function": "get_local_news", "country": "GB", "language": "en", "filename": "local.json"}
        with self.assertRaises(ValueError):
            source_to_search_config(source, "uknews")


class TestTopNewsFeedUrl(unittest.TestCase):
    def test_top_mode_builds_root_feed(self):
        url = build_feed_url({"mode": "top", "country": "US", "language": "en"})
        self.assertEqual(url, "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")


class TestLocalNewsFeedUrl(unittest.TestCase):
    def test_location_builds_geo_feed(self):
        url = build_feed_url({"location": "London", "country": "GB", "language": "en"})
        self.assertEqual(url, "https://news.google.com/rss/headlines/section/geo/London?hl=en-GB&gl=GB&ceid=GB:en")


class TestLoadApps(unittest.TestCase):
    def _write(self, tmpdir, app_cfg, index_filename="config_test.json"):
        apps_dir = os.path.join(tmpdir, "apps")
        os.makedirs(apps_dir, exist_ok=True)
        with open(os.path.join(apps_dir, index_filename), "w", encoding="utf-8") as f:
            json.dump(app_cfg, f)
        index_path = os.path.join(tmpdir, "apps.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({"apps": [index_filename]}, f)
        return index_path, apps_dir

    def test_topics_and_locations_become_news_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path, apps_dir = self._write(tmpdir, {
                "app_name": "uknews",
                "repository": "x/y",
                "topics": [{"topic": "NATION", "filename": "uk_national_news.json"}],
                "locations": [{"topic": "London", "filename": "uk_london_news.json"}],
            })
            apps = load_apps(index_path, apps_dir)

        self.assertEqual(len(apps), 1)
        sources = apps[0]["news_sources"]
        self.assertEqual(len(sources), 2)

        topic_source = next(s for s in sources if s["function"] == "get_news_by_topic")
        self.assertEqual(topic_source["topic"], "NATION")
        self.assertEqual(topic_source["filename"], "uk_national_news.json")
        self.assertEqual(topic_source["country"], DEFAULT_COUNTRY)
        self.assertEqual(topic_source["language"], DEFAULT_LANGUAGE)
        self.assertEqual(topic_source["max_results"], DEFAULT_MAX_RESULTS)

        location_source = next(s for s in sources if s["function"] == "get_local_news")
        self.assertEqual(location_source["location"], "London")
        self.assertEqual(location_source["filename"], "uk_london_news.json")

    def test_app_with_no_topics_or_locations_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path, apps_dir = self._write(tmpdir, {"app_name": "empty", "repository": "x/y"})
            apps = load_apps(index_path, apps_dir)
        self.assertEqual(apps, [])


if __name__ == "__main__":
    unittest.main()
