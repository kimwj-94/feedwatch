from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PBKDF2_ITERATIONS = 200_000


class CryptoError(RuntimeError):
    pass


# 자격증명은 '수집 비밀번호(passphrase)' 한 가지 방식으로만 암호화한다(웹 입력 ↔ 크롤러 복호화).


class PassphraseCipher:
    """패스프레이즈 기반 AES-256-GCM. 브라우저 WebCrypto(web/js/util/crypto.js)와 동일 포맷:
    PBKDF2-HMAC-SHA256(passphrase, salt, 200k) → 32B 키, blob = base64(salt[16] + iv[12] + ct||tag).
    웹 관리자가 자격증명을 입력하면 브라우저가 암호화해 저장하고, 크롤러가 같은 패스프레이즈로 복호화한다."""

    def __init__(self, passphrase: str, iterations: int = PBKDF2_ITERATIONS):
        if not passphrase:
            raise CryptoError("FEEDWATCH_CRED_PASSPHRASE(수집 비밀번호)가 설정되지 않았습니다.")
        self._passphrase = passphrase.encode("utf-8")
        self._iterations = iterations

    def _key(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._passphrase, salt, self._iterations, 32)

    def encrypt(self, plain_text: str) -> str:
        salt, iv = os.urandom(16), os.urandom(12)
        ciphertext = AESGCM(self._key(salt)).encrypt(iv, plain_text.encode("utf-8"), None)
        return base64.b64encode(salt + iv + ciphertext).decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        try:
            raw = base64.b64decode(encrypted_text.encode("utf-8"))
            salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
            return AESGCM(self._key(salt)).decrypt(iv, ciphertext, None).decode("utf-8")
        except (ValueError, InvalidTag) as exc:
            raise CryptoError("자격증명 복호화 실패. 수집 비밀번호(FEEDWATCH_CRED_PASSPHRASE)를 확인하세요.") from exc
