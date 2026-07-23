# FeedWatch v2 운영 전 체크리스트

자세한 절차는 [docs/SETUP_web.md](docs/SETUP_web.md) 참고.

## 1. Firebase
- [ ] Firebase 프로젝트 생성, Firestore 데이터베이스 생성(프로덕션 모드)
- [ ] Authentication 활성화: 이메일/비밀번호 + Google
- [ ] 웹 클라이언트 설정을 `web/firebase_config.json` 으로 저장(`web/firebase_config.example.json` 형식)
- [ ] 서비스 계정 키를 `service_account.json` 으로 저장(크롤러·관리자 등록용)
- [ ] `firestore.rules` 내용을 콘솔 → Firestore → **규칙** 탭에 붙여넣고 **게시**

## 2. 첫 관리자 부트스트랩
- [ ] 앱에서 본인 로그인(→ 승인 대기 화면이 떠도 계정은 생성됨)
- [ ] `py -m scripts.make_admin --email 내이메일` 실행 → `users/{uid}` 관리자 문서 + 기본 구분값 생성
- [ ] 새로고침하면 관리자 입장. 이후 가족은 **가입 신청 → 승인**으로 추가(또는 사용자 관리에서 등록)

## 3. Google API (필요 시)
- [ ] 이메일 발송용 SMTP 또는 Gmail API 준비
- [ ] (선택) YouTube Data API v3 → `YOUTUBE_API_KEY`. 채널 URL만으로 수집되므로 보통 불필요

## 4. 보안 값 / Secrets
- [ ] (로그인 필요 사이트가 있을 때) 웹 → URL 관리에서 아이디/비번 입력 시 정한 **‘수집 비밀번호’** 기록
- [ ] `.env` 작성(`.env.example` 참고) — 로컬 실행용
- [ ] GitHub Secrets: `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `FEEDWATCH_ADMIN_EMAIL`,
      `SMTP_*`, (선택) `YOUTUBE_API_KEY`, `FEEDWATCH_CRED_PASSPHRASE`
- [ ] 메일이 실제로 나가려면 웹 → 설정 → 이메일 발송 방식이 **`자동`** 이거나 `smtp`/`gmail` 이어야 함
      (`preview`면 파일만 생성되고 발송되지 않음)

## 5. 모니터링 URL (웹 관리자 → URL 관리)
- [ ] 일반: CSS 선택자가 게시글 링크를 정확히 잡는지
- [ ] 유튜브: 채널 URL 또는 `channel_id`
- [ ] 네이버 블로그: RSS 동작 / 카페: iframe·선택자(필요 시 쿠키)
- [ ] 로그인 사이트: 로그인 선택자 + 게시글 선택자, 웹에서 아이디/비번 등록(‘로그인정보 등록됨’ 확인)
- [ ] 선택자 확인은 `python -m crawler.main_crawler --source <id>` 로그로 점검

## 6. 로컬 점검
```powershell
.\.venv\Scripts\python.exe .\scripts\validate_setup.py
.\.venv\Scripts\python.exe -m crawler.main_crawler
```
웹 관리자 → 설정 → 환경 진단도 확인.

## 7. 배포 / 접속
- [ ] GitHub 공개 저장소 생성 → 업로드 → Settings → Pages → Source = **GitHub Actions**
- [ ] `Deploy web app (GitHub Pages)` 워크플로 실행 → `https://<아이디>.github.io/<저장소>/`
- [ ] 그 도메인을 **Authentication → 설정 → 승인된 도메인**에 추가(빠뜨리면 Google 로그인 실패)
- [ ] PC·휴대폰에서 로그인(이메일/Google) 확인
- [ ] 신규 표시 / 읽음·삭제·복원 상태가 가족 간 실시간 동기화되는지 확인
- [ ] 이메일 알림(미리보기 또는 실제 발송) 확인
- [ ] GitHub Actions 수동 1회 실행(Run workflow) 후 신규 항목 수집 확인

## 8. 인트라넷 대상(해당 시)
- [ ] 사내망 사이트는 내부망 PC에서 크롤러를 직접/스케줄 실행(외부망 Actions 불가)

---
> v1.0 데스크톱(exe) 운영은 `legacy/v1.0_desktop/`(소스 + `dist/` 빌드 산출물) 참고(보존용).
