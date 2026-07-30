from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawler.main_crawler import public_error_message, run
from shared.config import Settings
from shared.models import Group, Item, Source


def make_settings(temp_dir: str) -> Settings:
    root = Path(temp_dir)
    return Settings(
        storage="local",
        local_store=root / "store.json",
        admin_email="admin@example.com",
        firebase_project_id="",
        firebase_api_key="",
        youtube_api_key="",
        cred_passphrase="",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="sender@example.com",
        smtp_password="secret",
        smtp_from="sender@example.com",
        email_provider="smtp",
        app_url="https://example.com/feedwatch/",
        gmail_credentials=root / "client_secret.json",
        gmail_token=root / "token.json",
        google_oauth_credentials=root / "oauth.json",
        google_oauth_token=root / "oauth_token.json",
        crawl_min_delay=0,
        crawl_max_delay=0,
        playwright_headless=True,
    )


class FakeRepository:
    def __init__(self, source: Source, item: Item) -> None:
        self.source = source
        self.item = item
        self.logs = []

    def get_app_config(self):
        return {
            "auto_archive_days": 7,
            "trash_retention_days": 30,
            "email_enabled": True,
            "email_provider": "",
        }

    def archive_old_new_items(self, days=7):
        return 0

    def list_items(self, status=None):
        return []

    def permanently_delete_item(self, item_id):
        raise AssertionError("nothing should be purged")

    def list_sources(self, active_only=False):
        return [self.source]

    def list_groups(self):
        return [Group(id="group_common", name="공통", order=1)]

    def save_source(self, source):
        self.source = source
        return source

    def add_items_dedup(self, items):
        return list(items)

    def list_users(self):
        return []

    def save_log(self, log):
        self.logs.append(log)
        return log


class FirstCrawlTests(unittest.TestCase):
    def test_public_error_message_redacts_urls_and_secret_query_values(self) -> None:
        message = "GET https://private.example.com/path?token=secret failed password=hunter2"
        redacted = public_error_message(message)
        self.assertNotIn("private.example.com", redacted)
        self.assertNotIn("hunter2", redacted)

    def test_first_crawl_is_marked_complete_only_after_items_are_saved(self) -> None:
        source = Source(
            id="src_1",
            name="Example",
            url="https://example.com",
            group_ids=["group_common"],
        )
        item = Item(
            id="item_1",
            source_id=source.id,
            source_name=source.name,
            group_ids=source.group_ids,
            title="Existing post",
            url="https://example.com/post",
            hash="hash-1",
        )
        repository = FakeRepository(source, item)

        def fail_to_save(_items):
            raise RuntimeError("database unavailable")

        repository.add_items_dedup = fail_to_save
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("crawler.main_crawler.load_settings", return_value=make_settings(temp_dir)),
                patch("crawler.main_crawler.get_repository", return_value=repository),
                patch("crawler.main_crawler.crawl_with_retry", return_value=[item]),
            ):
                with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                    run()

        self.assertFalse(repository.source.first_crawl_done)

    def test_first_crawl_items_are_saved_but_not_queued_for_email(self) -> None:
        source = Source(
            id="src_1",
            name="Example",
            url="https://example.com",
            group_ids=["group_common"],
        )
        item = Item(
            id="item_1",
            source_id=source.id,
            source_name=source.name,
            group_ids=source.group_ids,
            title="Existing post",
            url="https://example.com/post",
            hash="hash-1",
        )
        repository = FakeRepository(source, item)
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("crawler.main_crawler.load_settings", return_value=make_settings(temp_dir)),
                patch("crawler.main_crawler.get_repository", return_value=repository),
                patch("crawler.main_crawler.crawl_with_retry", return_value=[item]),
                patch("crawler.main_crawler.queue_new_item_notifications") as queue,
                patch("crawler.main_crawler.deliver_pending_notifications", return_value=[]),
            ):
                code = run()

        self.assertEqual(code, 0)
        self.assertTrue(repository.source.first_crawl_done)
        queue.assert_not_called()
        self.assertEqual(repository.logs[0].new_items_count, 1)


if __name__ == "__main__":
    unittest.main()
