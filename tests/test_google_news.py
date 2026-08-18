import unittest

from src.google_news import build_feed_url


class TestBuildFeedUrl(unittest.TestCase):
    def test_query_search(self):
        url = build_feed_url({"query": "artificial intelligence", "country": "US", "language": "en"})
        self.assertIn("rss/search?q=artificial%20intelligence", url)
        self.assertIn("hl=en-US", url)
        self.assertIn("gl=US", url)
        self.assertIn("ceid=US:en", url)

    def test_named_topic(self):
        url = build_feed_url({"topic": "technology", "country": "US", "language": "en"})
        self.assertIn("rss/headlines/section/topic/TECHNOLOGY", url)

    def test_topic_url(self):
        topic_url = "https://news.google.com/topics/CAAqJggKIiBDQkFT?hl=en-US&gl=US&ceid=US:en"
        url = build_feed_url({"topic_url": topic_url, "country": "US", "language": "en"})
        self.assertIn("rss/topics/CAAqJggKIiBDQkFT", url)

    def test_missing_search_terms_raises(self):
        with self.assertRaises(ValueError):
            build_feed_url({"country": "US", "language": "en"})


if __name__ == "__main__":
    unittest.main()
