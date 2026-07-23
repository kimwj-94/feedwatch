from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]

WEB_FIREBASE_CONFIG = ROOT_DIR / "web" / "firebase_config.json"


@dataclass(frozen=True)
class Settings:
    storage: str
    local_store: Path
    admin_email: str
    firebase_project_id: str
    firebase_api_key: str
    youtube_api_key: str
    cred_passphrase: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    email_provider: str
    gmail_credentials: Path
    gmail_token: Path
    google_oauth_credentials: Path
    google_oauth_token: Path
    crawl_min_delay: int
    crawl_max_delay: int
    playwright_headless: bool


def load_settings() -> Settings:
    if load_dotenv:
        load_dotenv(ROOT_DIR / ".env")
    local_store = Path(os.getenv("FEEDWATCH_LOCAL_STORE", "data/local_store.json"))
    if not local_store.is_absolute():
        local_store = ROOT_DIR / local_store
    gmail_credentials = Path(os.getenv("GMAIL_CLIENT_SECRET_FILE", "client_secret.json"))
    gmail_token = Path(os.getenv("GMAIL_TOKEN_FILE", "token.json"))
    google_oauth_credentials = Path(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "client_secret.json"))
    google_oauth_token = Path(os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "google_login_token.json"))
    if not gmail_credentials.is_absolute():
        gmail_credentials = ROOT_DIR / gmail_credentials
    if not gmail_token.is_absolute():
        gmail_token = ROOT_DIR / gmail_token
    if not google_oauth_credentials.is_absolute():
        google_oauth_credentials = ROOT_DIR / google_oauth_credentials
    if not google_oauth_token.is_absolute():
        google_oauth_token = ROOT_DIR / google_oauth_token
    firebase_api_key = os.getenv("FIREBASE_API_KEY", "")
    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    # 웹앱이 쓰는 web/firebase_config.json이 정식 위치. 루트는 예전 위치(호환).
    for config_path in (WEB_FIREBASE_CONFIG, ROOT_DIR / "firebase_config.json"):
        if config_path.exists():
            import json

            config = json.loads(config_path.read_text(encoding="utf-8"))
            firebase_api_key = firebase_api_key or config.get("apiKey", "")
            firebase_project_id = firebase_project_id or config.get("projectId", "")
            break
    return Settings(
        storage=os.getenv("FEEDWATCH_STORAGE", "local").lower(),
        local_store=local_store,
        admin_email=os.getenv("FEEDWATCH_ADMIN_EMAIL", "admin@example.com"),
        firebase_project_id=firebase_project_id,
        firebase_api_key=firebase_api_key,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        cred_passphrase=os.getenv("FEEDWATCH_CRED_PASSPHRASE", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        email_provider=os.getenv("EMAIL_PROVIDER", "preview").lower(),
        gmail_credentials=gmail_credentials,
        gmail_token=gmail_token,
        google_oauth_credentials=google_oauth_credentials,
        google_oauth_token=google_oauth_token,
        crawl_min_delay=int(os.getenv("CRAWL_MIN_DELAY_SECONDS", "3")),
        crawl_max_delay=int(os.getenv("CRAWL_MAX_DELAY_SECONDS", "5")),
        playwright_headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() not in {"0", "false", "no"},
    )
