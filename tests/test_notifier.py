from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawler.notifier import (
    _filter_for_user,
    build_email_html,
    deliver_pending_notifications,
    notify_failures,
    queue_new_item_notifications,
)
from shared.config import Settings
from shared.models import Item, User
from shared.repository import LocalJsonRepository


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
        gmail_credentials=root / "client_secret.json",
        gmail_token=root / "token.json",
        google_oauth_credentials=root / "oauth.json",
        google_oauth_token=root / "oauth_token.json",
        crawl_min_delay=0,
        crawl_max_delay=0,
        playwright_headless=True,
    )


def make_item() -> Item:
    return Item(
        id="item_1",
        source_id="src_1",
        source_name="Example",
        group_ids=["group_common"],
        title="<script>alert(1)</script>",
        url='https://example.com/?q="unsafe"',
        hash="hash-1",
    )


class NotifierTests(unittest.TestCase):
    def test_empty_subscription_receives_nothing(self) -> None:
        user = User(id="user_1", name="User", email="user@example.com", notify_sources=[])
        self.assertEqual(_filter_for_user([make_item()], user), [])

    def test_subscription_filters_by_source(self) -> None:
        user = User(id="user_1", name="User", email="user@example.com", notify_sources=["src_1"])
        self.assertEqual(_filter_for_user([make_item()], user), [make_item()])

    def test_email_html_escapes_feed_content(self) -> None:
        body = build_email_html([make_item()])
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&quot;unsafe&quot;", body)

    def test_failure_notification_is_sent_to_every_admin(self) -> None:
        admins = [
            User(id=f"admin_{index}", name=f"Admin {index}", email=f"admin{index}@example.com", role="admin")
            for index in range(3)
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("crawler.notifier._send", return_value=(True, "")) as send:
                preview = notify_failures(
                    make_settings(temp_dir),
                    admins,
                    [("Broken source", "timeout")],
                )

        self.assertIsNone(preview)
        self.assertEqual(send.call_count, 3)

    def test_failed_delivery_stays_queued_and_is_retried(self) -> None:
        user = User(
            id="user_1",
            name="User",
            email="user@example.com",
            notify_sources=["src_1"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = LocalJsonRepository(Path(temp_dir) / "store.json", "admin@example.com")
            settings = make_settings(temp_dir)
            queue_new_item_notifications(repository, [user], [make_item()])
            queue_new_item_notifications(repository, [user], [make_item()])
            self.assertEqual(len(repository.list_notification_jobs()), 1)

            with patch("crawler.notifier._send", return_value=(False, "temporary error")):
                notes = deliver_pending_notifications(settings, repository)

            queued = repository.list_notification_jobs()
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0].attempts, 1)
            self.assertIn("temporary error", notes[0])

            with patch("crawler.notifier._send", return_value=(True, "")) as send:
                notes = deliver_pending_notifications(settings, repository)

            self.assertEqual(notes, [])
            self.assertEqual(send.call_count, 1)
            self.assertEqual(repository.list_notification_jobs(), [])


if __name__ == "__main__":
    unittest.main()
