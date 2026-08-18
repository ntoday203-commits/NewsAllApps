import unittest

from src.utils import canonicalize_url, generate_article_id


class TestCanonicalizeUrl(unittest.TestCase):
    def test_strips_tracking_params(self):
        url = "https://Example.com/Article/?utm_source=twitter&id=42"
        self.assertEqual(canonicalize_url(url), "https://example.com/Article?id=42")

    def test_strips_trailing_slash_and_fragment(self):
        url = "https://example.com/article/#section-2"
        self.assertEqual(canonicalize_url(url), "https://example.com/article")

    def test_ignores_query_param_order(self):
        a = canonicalize_url("https://example.com/a?b=2&a=1")
        b = canonicalize_url("https://example.com/a?a=1&b=2")
        self.assertEqual(a, b)


class TestGenerateArticleId(unittest.TestCase):
    def test_deterministic(self):
        url = "https://example.com/article?id=1"
        self.assertEqual(generate_article_id(url), generate_article_id(url))

    def test_tracking_params_do_not_change_id(self):
        base = generate_article_id("https://example.com/article")
        with_tracking = generate_article_id("https://example.com/article?utm_source=x")
        self.assertEqual(base, with_tracking)

    def test_different_urls_different_ids(self):
        a = generate_article_id("https://example.com/a")
        b = generate_article_id("https://example.com/b")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
