from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from crawler.naver import _build_session
from shared.crypto import PassphraseCipher
from shared.models import Credential, Source
from shared.repository import LocalJsonRepository


class NaverCredentialTests(unittest.TestCase):
    def test_encrypted_cookie_is_decrypted_only_for_crawler_session(self) -> None:
        passphrase = "family-secret"
        cookie = "NID_AUT=encrypted-cookie; NID_SES=session-cookie"
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = LocalJsonRepository(Path(temp_dir) / "store.json", "admin@example.com")
            repository.save_credential(
                Credential(
                    id="cred_1",
                    source_id="src_1",
                    cookie_encrypted=PassphraseCipher(passphrase).encrypt(cookie),
                )
            )
            source = Source(
                id="src_1",
                name="Private cafe",
                url="https://cafe.naver.com/example",
                group_ids=["group_common"],
                type="naver",
                credential_id="cred_1",
            )

            session = _build_session(
                source,
                repository,
                SimpleNamespace(cred_passphrase=passphrase),
            )

        self.assertEqual(session.headers["Cookie"], cookie)
        self.assertNotIn("cookie", source.metadata)

    def test_legacy_plaintext_cookie_remains_readable_during_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = LocalJsonRepository(Path(temp_dir) / "store.json", "admin@example.com")
            source = Source(
                id="src_1",
                name="Legacy cafe",
                url="https://cafe.naver.com/example",
                group_ids=["group_common"],
                type="naver",
                metadata={"cookie": "legacy-cookie"},
            )

            session = _build_session(
                source,
                repository,
                SimpleNamespace(cred_passphrase=""),
            )

        self.assertEqual(session.headers["Cookie"], "legacy-cookie")


if __name__ == "__main__":
    unittest.main()
