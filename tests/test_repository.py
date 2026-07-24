from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shared.models import Credential, Item, Source
from shared.repository import LocalJsonRepository


def make_item(item_id: str, fingerprint: str) -> Item:
    return Item(
        id=item_id,
        source_id="src_1",
        source_name="Example",
        group_ids=["group_common"],
        title="Title",
        url="https://example.com/post",
        hash=fingerprint,
    )


class LocalRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(self.temp_dir.name) / "store.json"
        self.repository = LocalJsonRepository(path, "admin@example.com")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_items_dedup_ignores_existing_items(self) -> None:
        self.repository.add_items_dedup([make_item("item_1", "same-hash")])

        added = self.repository.add_items_dedup([make_item("item_2", "same-hash")])

        self.assertEqual(added, [])
        self.assertEqual(len(self.repository.list_items()), 1)

    def test_add_items_dedup_deduplicates_current_batch(self) -> None:
        added = self.repository.add_items_dedup(
            [
                make_item("item_1", "same-hash"),
                make_item("item_2", "same-hash"),
            ]
        )

        self.assertEqual(len(added), 1)
        self.assertEqual(len(self.repository.list_items()), 1)

    def test_deleting_source_also_deletes_its_credential(self) -> None:
        credential = self.repository.save_credential(
            Credential(
                id="cred_1",
                source_id="src_1",
                username_encrypted="encrypted-user",
                password_encrypted="encrypted-password",
            )
        )
        self.repository.save_source(
            Source(
                id="src_1",
                name="Private source",
                url="https://example.com/login",
                group_ids=["group_common"],
                type="login_required",
                credential_id=credential.id,
            )
        )

        self.repository.delete_source("src_1")

        self.assertIsNone(self.repository.get_credential(credential.id))


if __name__ == "__main__":
    unittest.main()
