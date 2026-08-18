import unittest

from src.apps_config import source_to_search_config
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


if __name__ == "__main__":
    unittest.main()
