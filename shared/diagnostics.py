from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from shared.config import ROOT_DIR, WEB_FIREBASE_CONFIG, Settings, load_settings


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: str
    message: str


def run_diagnostics(settings: Settings | None = None) -> list[DiagnosticCheck]:
    settings = settings or load_settings()
    checks = [
        _check_python(),
        _check_required_modules(),
        _check_env_file(),
        _check_local_store(settings),
        _check_firebase_client(settings),
        _check_firestore_service_account(settings),
        _check_auth_settings(settings),
        _check_email_settings(settings),
        _check_youtube_settings(settings),
        _check_cred_passphrase(settings),
        _check_playwright(),
    ]
    return checks


def diagnostics_summary(checks: list[DiagnosticCheck]) -> str:
    counts = {status: sum(1 for check in checks if check.status == status) for status in ["OK", "WARN", "FAIL"]}
    lines = [f"OK {counts['OK']} / WARN {counts['WARN']} / FAIL {counts['FAIL']}"]
    for check in checks:
        lines.append(f"[{check.status}] {check.name}: {check.message}")
    return "\n".join(lines)


def diagnostics_exit_code(checks: list[DiagnosticCheck]) -> int:
    return 1 if any(check.status == "FAIL" for check in checks) else 0


def _check_python() -> DiagnosticCheck:
    version = sys.version_info
    if version >= (3, 11):
        return DiagnosticCheck("Python", "OK", f"{version.major}.{version.minor}.{version.micro}")
    return DiagnosticCheck("Python", "FAIL", "Python 3.11 이상이 필요합니다.")


def _check_required_modules() -> DiagnosticCheck:
    # v2 웹앱은 customtkinter가 필요 없음(레거시 데스크톱 전용). 크롤러/백엔드 패키지만 점검.
    required = ["requests", "bs4", "feedparser", "cryptography", "firebase_admin"]
    optional = ["googleapiclient", "google_auth_oauthlib"]  # 유튜브 API 폴백 · Gmail 발송에만 필요
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        return DiagnosticCheck("Python 패키지", "FAIL", "누락: " + ", ".join(missing))
    missing_optional = [name for name in optional if importlib.util.find_spec(name) is None]
    if missing_optional:
        return DiagnosticCheck("Python 패키지", "WARN", "필수는 모두 있음. 선택 패키지 없음: " + ", ".join(missing_optional))
    return DiagnosticCheck("Python 패키지", "OK", "필수 패키지가 설치되어 있습니다.")


def _check_env_file() -> DiagnosticCheck:
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        return DiagnosticCheck(".env", "OK", str(env_path))
    return DiagnosticCheck(".env", "WARN", ".env가 없습니다. 로컬 기본값으로 실행됩니다.")


def _check_local_store(settings: Settings) -> DiagnosticCheck:
    if settings.storage != "local":
        return DiagnosticCheck("로컬 저장소", "OK", f"현재 저장소 모드: {settings.storage}")
    try:
        settings.local_store.parent.mkdir(parents=True, exist_ok=True)
        if settings.local_store.exists():
            json.loads(settings.local_store.read_text(encoding="utf-8"))
            return DiagnosticCheck("로컬 저장소", "OK", str(settings.local_store))
        return DiagnosticCheck("로컬 저장소", "WARN", f"아직 생성되지 않았습니다: {settings.local_store}")
    except Exception as exc:
        return DiagnosticCheck("로컬 저장소", "FAIL", str(exc))


def _check_firebase_client(settings: Settings) -> DiagnosticCheck:
    if settings.firebase_api_key and settings.firebase_project_id:
        return DiagnosticCheck("Firebase 클라이언트 설정", "OK", settings.firebase_project_id)
    if WEB_FIREBASE_CONFIG.exists():
        return DiagnosticCheck("Firebase 클라이언트 설정", "WARN", "web/firebase_config.json은 있지만 apiKey/projectId가 비어 있습니다.")
    return DiagnosticCheck("Firebase 클라이언트 설정", "WARN", "web/firebase_config.json이 없어 웹앱은 데모 모드로 동작합니다.")


def _check_firestore_service_account(settings: Settings) -> DiagnosticCheck:
    if settings.storage != "firestore":
        return DiagnosticCheck("Firestore Admin 설정", "OK", "local 모드에서는 필수가 아닙니다.")
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path:
        return DiagnosticCheck("Firestore Admin 설정", "FAIL", "GOOGLE_APPLICATION_CREDENTIALS가 비어 있습니다.")
    path = Path(cred_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if path.exists():
        return DiagnosticCheck("Firestore Admin 설정", "OK", str(path))
    return DiagnosticCheck("Firestore Admin 설정", "FAIL", f"서비스 계정 파일을 찾을 수 없습니다: {path}")


def _check_auth_settings(settings: Settings) -> DiagnosticCheck:
    # v2는 브라우저에서 Firebase Auth(이메일/비번 + Google)로 로그인한다. 별도 OAuth 클라이언트 파일은 불필요.
    if settings.firebase_api_key:
        return DiagnosticCheck("로그인 설정", "OK", "Firebase 이메일/비밀번호 · Google 로그인을 사용할 수 있습니다.")
    return DiagnosticCheck("로그인 설정", "WARN", "web/firebase_config.json이 없으면 웹앱은 데모 모드로 동작합니다.")


def _check_email_settings(settings: Settings) -> DiagnosticCheck:
    if settings.email_provider == "gmail":
        if settings.gmail_credentials.exists():
            return DiagnosticCheck("이메일 알림", "OK", "Gmail API 설정 파일이 있습니다.")
        return DiagnosticCheck("이메일 알림", "WARN", f"Gmail API 설정 파일이 없습니다: {settings.gmail_credentials}")
    if settings.email_provider == "smtp":
        required = [settings.smtp_host, settings.smtp_username, settings.smtp_password]
        if all(required):
            return DiagnosticCheck("이메일 알림", "OK", f"SMTP: {settings.smtp_host}")
        return DiagnosticCheck("이메일 알림", "WARN", "SMTP 설정값이 일부 비어 있습니다.")
    return DiagnosticCheck("이메일 알림", "OK", "preview 모드입니다. data/last_email_preview.html을 생성합니다.")


def _check_youtube_settings(settings: Settings) -> DiagnosticCheck:
    # 채널 URL → 채널ID 자동추출 + 채널 RSS로 수집하므로 키는 폴백용(선택)이다.
    if settings.youtube_api_key:
        return DiagnosticCheck("YouTube", "OK", "채널 RSS 수집 + API 키 폴백까지 준비되었습니다.")
    return DiagnosticCheck("YouTube", "OK", "채널 URL만으로 수집합니다(API 키는 선택).")


def _check_cred_passphrase(settings: Settings) -> DiagnosticCheck:
    if settings.cred_passphrase:
        return DiagnosticCheck("수집 비밀번호", "OK", "FEEDWATCH_CRED_PASSPHRASE가 설정되어 있습니다.")
    return DiagnosticCheck("수집 비밀번호", "WARN", "로그인 필요 사이트를 쓰려면 FEEDWATCH_CRED_PASSPHRASE(웹의 '수집 비밀번호'와 동일)가 필요합니다.")


def _check_playwright() -> DiagnosticCheck:
    if importlib.util.find_spec("playwright") is None:
        return DiagnosticCheck("Playwright", "WARN", "패키지가 없습니다. 로그인 사이트 크롤링 전 설치가 필요합니다.")
    return DiagnosticCheck("Playwright", "OK", "패키지가 설치되어 있습니다.")
