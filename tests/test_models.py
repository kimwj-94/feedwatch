from __future__ import annotations

import unittest

from shared.models import Source, from_dict, item_hash


class ItemHashTests(unittest.TestCase):
    def test_guid_has_priority_over_url_and_title(self) -> None:
        first = item_hash("source", "old title", "https://example.com/old", "guid-1")
        second = item_hash("source", "new title", "https://example.com/new", "guid-1")
        self.assertEqual(first, second)

    def test_url_has_priority_over_title_without_guid(self) -> None:
        first = item_hash("source", "old title", "https://example.com/post")
        second = item_hash("source", "corrected title", "https://example.com/post")
        self.assertEqual(first, second)

    def test_source_is_part_of_fingerprint(self) -> None:
        first = item_hash("source-a", "title", "https://example.com/post")
        second = item_hash("source-b", "title", "https://example.com/post")
        self.assertNotEqual(first, second)


class SchemaCompatibilityTests(unittest.TestCase):
    def test_unknown_fields_are_ignored_and_legacy_group_is_migrated(self) -> None:
        source = from_dict(
            Source,
            {
                "id": "src_1",
                "name": "Example",
                "url": "https://example.com",
                "group_id": "group_old",
                "colorIndex": 4,
            },
        )

        self.assertEqual(source.group_ids, ["group_old"])
        self.assertFalse(hasattr(source, "colorIndex"))


if __name__ == "__main__":
    unittest.main()
