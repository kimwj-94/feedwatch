# FeedWatch v1.0 — 데스크톱(CustomTkinter) 보존본

이 폴더는 **FeedWatch v1.0의 데스크톱 UI 소스를 그대로 보존**한 것입니다.
v2.0부터 화면은 `web/`의 웹 대시보드로 교체되었고, 이 데스크톱 버전은 참고/롤백용으로만 남겨둡니다.

## 무엇이 들어 있나
- `app/` — CustomTkinter 데스크톱 앱 소스 (진입점 `app/main.py`, 로그인/대시보드/관리자 UI)
- `FeedWatch.spec`, `scripts/build_exe.ps1`, `scripts/create_setup_package.ps1` — 데스크톱 exe 빌드/패키징 스크립트

## 실행/빌드 시 주의 (중요)
이 소스는 **저장소 루트 레이아웃을 가정**합니다. 즉 `shared/`, `crawler/`, `data/`, `.venv/`는
여전히 저장소 루트(`FeedWatch/`)에 있고, v2 웹앱·크롤러와 공유합니다.
`app/main.py`는 `parents[1]`을 `sys.path`에 넣어 `shared`를 import하므로, 이 폴더 위치에서 그대로
실행하면 `shared`를 찾지 못합니다.

따라서:
- **정식 실행본은 이미 빌드된 `dist/FeedWatch.exe` / `dist/FeedWatch_v1.0_Setup.zip`** 입니다. 데스크톱이
  필요하면 그 산출물을 쓰세요.
- 소스에서 재빌드가 꼭 필요하면, 이 `app/`·`*.spec`·빌드 스크립트를 저장소 루트로 되돌린 뒤
  (원래 v1.0 레이아웃) PyInstaller를 실행하세요. 빌드 스크립트의 경로(`app\main.py`, 루트 `.venv`)도
  그 레이아웃 기준입니다.

## v2.0과의 관계
- 데이터 모델(`shared/models.py`), 크롤러(`crawler/`), Firestore 어댑터(`shared/firestore_repository.py`),
  보안 규칙(`firestore.rules`)은 **v1·v2가 동일하게 공유**합니다. 즉 백엔드는 그대로이고 화면만 바뀝니다.
- v1의 로그인/대시보드/관리자 동작은 v2 웹앱에 모두 이식되었으며, 기획서에 있었지만 v1에서 빠졌던
  기능(날짜 필터·상대시간·소스 편집·구분값 순서변경·사용자 알림설정·설정 편집 등)은 v2에서 구현되었습니다.
