import unittest

from src.processor import _is_complete


def _full_record(**overrides):
    record = {
        "title": "Some Title",
        "source": "Some Source",
        "author": "Some Author",
        "published_at": "2026-08-18T00:00:00+00:00",
        "image": "https://example.com/image.jpg",
        "url": "https://example.com/article",
        "content": "Full article text.",
        "summary": "A summary.",
        "key_points": ["point one"],
    }
    record.update(overrides)
    return record


class TestIsComplete(unittest.TestCase):
    def test_fully_populated_record_is_complete(self):
        self.assertTrue(_is_complete(_full_record()))

    def test_null_field_is_incomplete(self):
        self.assertFalse(_is_complete(_full_record(author=None)))

    def test_empty_string_field_is_incomplete(self):
        self.assertFalse(_is_complete(_full_record(summary="")))

    def test_empty_key_points_is_incomplete(self):
        self.assertFalse(_is_complete(_full_record(key_points=[])))

    def test_missing_field_entirely_is_incomplete(self):
        record = _full_record()
        del record["image"]
        self.assertFalse(_is_complete(record))


if __name__ == "__main__":
    unittest.main()
