"""첫 관리자 만들기 — Firebase 콘솔에서 UID를 직접 복사할 필요 없이 자동으로 등록한다.

보안 규칙이 users/{Auth uid} 문서로 관리자 여부를 확인하므로, 사용자 문서는 반드시
'로그인 계정의 uid'를 문서 ID로 써야 한다. 이 스크립트가 이메일로 uid를 찾아 대신 만들어 준다.

준비물
  1) service_account.json (콘솔 → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성)
  2) 관리자로 지정할 사람이 앱에서 **한 번 로그인**해 둔 상태(그래야 Auth에 계정이 생긴다)

사용
  py -m scripts.make_admin --list                    # Auth에 등록된 계정 목록 보기
  py -m scripts.make_admin --email me@gmail.com      # 그 계정을 관리자로 등록
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import load_settings
from shared.models import User, utc_now


def _prepare_credentials(settings) -> str | None:
    """GOOGLE_APPLICATION_CREDENTIALS를 절대경로로 고정한다(어느 폴더에서 실행해도 동작)."""
    raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return f"서비스 계정 키를 찾을 수 없습니다: {path}\n" \
               "Firebase 콘솔 → 프로젝트 설정 → 서비스 계정 → '새 비공개 키 생성'으로 받아 " \
               f"{ROOT / 'service_account.json'} 로 저장하세요."
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    if not settings.firebase_project_id:
        return "프로젝트 ID를 알 수 없습니다. web/firebase_config.json을 만들었는지, " \
               "또는 .env의 FIREBASE_PROJECT_ID가 채워졌는지 확인하세요."
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="FeedWatch 첫 관리자 등록")
    parser.add_argument("--email", help="관리자로 지정할 로그인 이메일")
    parser.add_argument("--name", default=None, help="표시 이름(생략 시 계정 이름 사용)")
    parser.add_argument("--list", action="store_true", help="Auth에 등록된 계정 목록만 보기")
    args = parser.parse_args()

    settings = load_settings()
    problem = _prepare_credentials(settings)
    if problem:
        print(problem)
        return 1

    from firebase_admin import auth

    from shared.firestore_repository import FirestoreRepository

    repository = FirestoreRepository(settings)

    if args.list or not args.email:
        print(f"프로젝트: {settings.firebase_project_id}")
        print("Firebase Auth에 등록된 계정:")
        found = False
        for user in auth.list_users().iterate_all():
            providers = ",".join(p.provider_id for p in (user.provider_data or [])) or "-"
            print(f"  - {user.email or '(이메일 없음)'}  [{providers}]  uid={user.uid}")
            found = True
        if not found:
            print("  (없음) — 앱에서 먼저 한 번 로그인하세요. '승인 대기' 화면이 떠도 계정은 생성됩니다.")
        if not args.email:
            print("\n관리자로 등록하려면: py -m scripts.make_admin --email <위 목록의 이메일>")
        return 0

    try:
        account = auth.get_user_by_email(args.email)
    except auth.UserNotFoundError:
        print(f"'{args.email}' 계정이 Firebase Auth에 없습니다.")
        print("앱을 열어 그 계정으로 한 번 로그인한 뒤(‘승인 대기’ 화면이 떠도 됩니다) 다시 실행하세요.")
        print("등록된 계정을 보려면: py -m scripts.make_admin --list")
        return 1

    # 같은 이메일의 옛 문서(크롤러가 만든 user_admin 등)가 있으면 uid 문서와 충돌하므로 정리한다.
    for existing in repository.list_users():
        if (existing.email or "").lower() == (account.email or "").lower() and existing.id != account.uid:
            repository._collection("users").document(existing.id).delete()
            print(f"· 같은 이메일의 옛 사용자 문서를 정리했습니다: {existing.id}")

    user = User(
        id=account.uid,
        name=args.name or account.display_name or (account.email or "").split("@")[0],
        email=account.email,
        role="admin",
        notify_email=True,
        last_login=utc_now(),
    )
    repository.save_user(user)
    print(f"✓ 관리자 등록 완료: {user.name} <{user.email}>  (users/{account.uid})")

    groups = repository.list_groups()  # 없으면 기본 구분값(공통·아빠·엄마) 자동 생성
    print(f"✓ 구분값 {len(groups)}개 준비됨: " + ", ".join(g.name for g in groups))
    print("\n이제 앱을 새로고침하면 관리자로 입장됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
