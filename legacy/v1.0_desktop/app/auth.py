from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from shared.config import Settings
from shared.models import User, utc_now
from shared.repository import BaseRepository


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthSession:
    user: User
    provider: str
    id_token: str | None = None
    refresh_token: str | None = None


class AuthService:
    def __init__(self, repository: BaseRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def list_local_users(self) -> list[User]:
        return sorted(self.repository.list_users(), key=lambda user: (user.role != "admin", user.name))

    def local_login(self, email: str) -> AuthSession:
        user = self._find_user(email)
        if not user:
            raise AuthError("등록된 사용자를 찾을 수 없습니다.")
        user.last_login = utc_now()
        self.repository.save_user(user)
        return AuthSession(user=user, provider="local")

    def firebase_email_login(self, email: str, password: str) -> AuthSession:
        if not self.settings.firebase_api_key:
            raise AuthError("Firebase API 키가 설정되지 않았습니다. firebase_config.json 또는 FIREBASE_API_KEY를 확인하세요.")
        endpoint = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            f"?key={self.settings.firebase_api_key}"
        )
        response = requests.post(
            endpoint,
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=20,
        )
        payload = response.json()
        if response.status_code >= 400:
            message = payload.get("error", {}).get("message", "Firebase login failed.")
            raise AuthError(_friendly_firebase_error(message))

        user = self._find_user(payload.get("email", email))
        if not user:
            raise AuthError("Firebase 로그인은 성공했지만 FeedWatch 사용자 목록에 등록되지 않은 계정입니다.")
        user.last_login = utc_now()
        self.repository.save_user(user)
        return AuthSession(
            user=user,
            provider="firebase",
            id_token=payload.get("idToken"),
            refresh_token=payload.get("refreshToken"),
        )

    def firebase_google_login(self) -> AuthSession:
        if not self.settings.firebase_api_key:
            raise AuthError("Firebase API 키가 설정되지 않았습니다. firebase_config.json 또는 FIREBASE_API_KEY를 확인하세요.")
        if not self.settings.google_oauth_credentials.exists():
            raise AuthError(f"Google OAuth 클라이언트 파일을 찾을 수 없습니다: {self.settings.google_oauth_credentials}")

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ModuleNotFoundError as exc:
            raise AuthError("Google OAuth 라이브러리가 설치되지 않았습니다. requirements.txt를 다시 설치하세요.") from exc

        scopes = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
        google_creds = None
        if self.settings.google_oauth_token.exists():
            google_creds = Credentials.from_authorized_user_file(str(self.settings.google_oauth_token), scopes)
        if not google_creds or not google_creds.valid:
            if google_creds and google_creds.expired and google_creds.refresh_token:
                google_creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.settings.google_oauth_credentials), scopes)
                google_creds = flow.run_local_server(port=0)
            self.settings.google_oauth_token.write_text(google_creds.to_json(), encoding="utf-8")

        if not google_creds.id_token:
            raise AuthError("Google OAuth 응답에서 ID 토큰을 받지 못했습니다. OAuth 클라이언트 설정을 확인하세요.")

        firebase_payload = self._firebase_sign_in_with_google(google_creds.id_token)
        email = firebase_payload.get("email")
        if not email:
            raise AuthError("Firebase Google 로그인 응답에서 이메일을 확인할 수 없습니다.")
        user = self._find_user(email)
        if not user:
            raise AuthError("Google 로그인은 성공했지만 FeedWatch 사용자 목록에 등록되지 않은 계정입니다.")
        user.last_login = utc_now()
        self.repository.save_user(user)
        return AuthSession(
            user=user,
            provider="google",
            id_token=firebase_payload.get("idToken"),
            refresh_token=firebase_payload.get("refreshToken"),
        )

    def _firebase_sign_in_with_google(self, google_id_token: str) -> dict:
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp" f"?key={self.settings.firebase_api_key}"
        post_body = urlencode({"id_token": google_id_token, "providerId": "google.com"})
        response = requests.post(
            endpoint,
            json={
                "postBody": post_body,
                "requestUri": "http://localhost",
                "returnIdpCredential": True,
                "returnSecureToken": True,
            },
            timeout=20,
        )
        payload = response.json()
        if response.status_code >= 400:
            message = payload.get("error", {}).get("message", "Firebase Google login failed.")
            raise AuthError(_friendly_firebase_error(message))
        return payload

    def _find_user(self, email: str) -> User | None:
        target = email.strip().lower()
        for user in self.repository.list_users():
            if user.email.lower() == target:
                return user
        return None


def _friendly_firebase_error(message: str) -> str:
    errors = {
        "EMAIL_NOT_FOUND": "등록되지 않은 Firebase 이메일입니다.",
        "INVALID_PASSWORD": "비밀번호가 올바르지 않습니다.",
        "USER_DISABLED": "비활성화된 Firebase 계정입니다.",
        "INVALID_LOGIN_CREDENTIALS": "이메일 또는 비밀번호가 올바르지 않습니다.",
    }
    return errors.get(message, message)
