# FeedWatch v2

여러 웹사이트(일반 공지·유튜브·네이버 카페/블로그·로그인 필요 사이트)의 **새 글을 자동 감지**해,
**가족이 하나의 대시보드에서 통합 확인**하고 이메일로 알림받는 개인 모니터링 시스템입니다.

v2부터 화면이 **브라우저 기반 웹 대시보드(`web/`)** 로 바뀌었습니다. 반응형이라 PC·태블릿·휴대폰에서
모두 열리고, Firebase로 가족 간 상태(읽음·삭제)가 실시간 공유됩니다. 크롤러·데이터모델·보안규칙 등
백엔드는 v1과 동일하게 유지·강화되었습니다.

> v1.0 데스크톱 앱(CustomTkinter)은 [`legacy/v1.0_desktop/`](legacy/v1.0_desktop/README.md) 에 보존되어 있습니다.

---

## 두 가지 실행 모드

| 모드 | 조건 | 저장소 | 용도 |
|---|---|---|---|
| **데모(DEMO)** | `web/firebase_config.json` 없음 | 브라우저 localStorage + 샘플 | 키 없이 즉시 체험·미리보기 |
| **클라우드(CLOUD)** | `web/firebase_config.json` 있음 | Firebase Firestore(실시간) | 실제 가족 운영 |

웹앱은 시작 시 `web/firebase_config.json` 존재 여부로 모드를 자동 판별합니다.

---

## 1. 데모 모드로 바로 체험

설정·키 없이 샘플 데이터로 모든 기능(대시보드·필터·관리·다크모드)을 둘러볼 수 있습니다.

- **가장 쉬운 방법**: 루트의 **`FeedWatch_데모실행.bat` 더블클릭** → 브라우저가 자동으로 열립니다.
- 수동 실행:
  ```powershell
  cd "D:\Users\vmfort\Desktop\개발\FeedWatch_v2"
  py scripts\devserver.py 5180 web
  ```
  그 후 브라우저에서 `http://localhost:5180`. (`devserver.py`는 브라우저 캐시를 끄므로 코드를 고쳐도 바로 반영됩니다.)

로그인 화면에서 계정을 고르면 됩니다(관리자 김우재 / 구성원 이수민·김하늘). 변경사항은 그 브라우저에만
저장되며, **관리 → 설정 → 데모 데이터 초기화**로 되돌립니다.

> `web/index.html`을 그냥 더블클릭하면 ES 모듈 정책(file://)으로 동작하지 않습니다. 반드시 위 방법으로 여세요.

---

## 2. 클라우드 모드 설정 (실제 운영)

비개발자용 단계별 안내는 **[docs/FeedWatch_클라우드_설치설명서.docx](docs/FeedWatch_클라우드_설치설명서.docx)** (Word, 그림자리·체크리스트 포함) 또는 [docs/SETUP_web.md](docs/SETUP_web.md) 를 참고하세요. 요약:

1. **Firebase 프로젝트 생성** → Firestore 데이터베이스 생성(프로덕션 모드).
2. **Authentication 활성화**: 이메일/비밀번호 + Google.
3. **웹 클라이언트 설정**을 `web/firebase_config.json` 으로 저장
   (`web/firebase_config.example.json` 형식: `apiKey`, `authDomain`, `projectId`, `appId`).
4. **보안 규칙 배포**: [`firestore.rules`](firestore.rules) 내용을 콘솔 → Firestore → **규칙** 탭에 붙여넣고 **게시**
   (CLI를 쓴다면 `firebase deploy --only firestore:rules`).
5. **첫 관리자 부트스트랩**(아래 "첫 관리자 만들기" 참고).
6. **웹앱 배포**: GitHub Pages(`Deploy web app` 워크플로) → 어느 기기에서나 접속.
   배포 주소의 도메인을 **Authentication → 승인된 도메인**에 추가해야 Google 로그인이 됩니다.
7. **크롤러 자동화**: GitHub Actions Secrets 등록 후 하루 2회 자동 실행(아래 4번).

### 로그인 / 가입 흐름

- 로그인 수단: **Google** 또는 **이메일/비밀번호**. 로그인 ID는 Google 계정이 기본입니다.
- 접근 통제: **관리자가 승인한 계정만** 입장합니다.
  - 미등록자가 로그인하면 자동으로 **가입 신청**이 생성되고 "승인 대기" 화면이 표시됩니다.
  - 관리자는 **관리자 → 가입 신청** 탭에서 승인/거절합니다.
  - Firebase 권한은 로그인 계정의 UID를 기준으로 하므로, 가족이 먼저 한 번 로그인해 가입 신청을 만든 뒤 승인해야 합니다.
- 본인 표시이름·알림 설정은 헤더 **프로필 → 내 설정**에서 누구나 직접 수정합니다.

### 첫 관리자 만들기 (부트스트랩)

사용자 문서는 **Firebase Auth uid로 키잉**됩니다(보안 규칙이 uid로 관리자 여부를 확인). 첫 관리자는 승인해 줄
관리자가 아직 없으므로 한 번만 직접 만듭니다. UID는 스크립트가 찾아 줍니다.

1. 앱을 열고 **본인 Google(또는 이메일/비번)로 로그인** → "승인 대기" 화면이 뜹니다(계정은 생성됨).
2. 콘솔 → 프로젝트 설정 → **서비스 계정** → 새 비공개 키를 받아 `service_account.json`으로 저장합니다.
3. `py -m scripts.make_admin --email 내이메일@gmail.com` 실행 → `users/{uid}` 관리자 문서 + 기본 구분값 생성.
4. 앱을 새로고침하면 관리자로 입장됩니다. 이후 다른 가족은 **가입 신청 → 승인**으로 추가합니다.

> 계정 목록이 헷갈리면 `py -m scripts.make_admin --list` 로 Auth에 등록된 이메일을 볼 수 있습니다.

> 크롤러가 자동 생성하는 기본 관리자(`FEEDWATCH_ADMIN_EMAIL`, 문서 ID `user_admin`)는 크롤러(Admin SDK)용이며,
> 웹에서 관리자 권한 인식은 위처럼 **uid 기반 문서**가 필요합니다. 기본 구분값(공통/아빠/엄마)은 크롤러 1회 실행으로 생성됩니다.

---

## 운영 모델 — 상시 켜둘 PC가 필요 없습니다

- **웹앱**: 정적 파일(Firebase Hosting 등) → 가족이 브라우저로 접속해 **Firestore에 직접 읽고/쓰기**. 서버·메인 PC 불필요.
- **새 글 수집(크롤러)**: **GitHub Actions 클라우드 cron**(하루 2회)에서 실행 → PC 없이 자동.
- **권한**: **승인된 가족이면 누구나** URL(소스)·구분값·항목을 **추가/수정/삭제**(메뉴 → 관리). 한 사이트에 **구분값을 여러 개** 지정할 수 있습니다(예: 병원 공지 = 공통 + 아빠). **관리자**는 추가로
  **가입 신청 승인·사용자 관리·설정**만 담당합니다. 즉 관리자는 "상시 실행"이 아니라 "역할"일 뿐, 아무 기기에서나 처리합니다.
- 로컬 실행이 필요한 경우는 사실상 하나: 외부망 Actions가 못 가는 **사내 인트라넷 사이트**뿐. (로그인 사이트 자격증명은 웹 화면에서 바로 등록됩니다.)

## 3. 디렉터리 구조

```
FeedWatch_v2/
├── FeedWatch_데모실행.bat   # 데모 원클릭 실행(web/ 서빙 + 브라우저 열기)
├── web/                  # v2 웹 대시보드(무빌드 정적 앱) ★ 사용자가 여는 것
│   ├── index.html        # 앱 셸
│   ├── css/              # tokens.css(디자인 토큰) · app.css(라이트/다크)
│   ├── js/
│   │   ├── main.js       # 부트스트랩(모드 판별·테마·로그인·라우팅)
│   │   ├── config.js     # firebase_config.json 유무로 cloud/demo 판별
│   │   ├── auth.js       # Google·이메일 로그인 + 가입신청 게이트
│   │   ├── data/         # adapter.js(계약) · local.js(데모) · firestore.js(클라우드)
│   │   ├── ui/           # shell.js(사이드바 통합 셸·피드·관리) · components.js
│   │   └── util/         # format(상대시간·필터) · dom · icons
│   └── sample/           # 데모 샘플 데이터
├── crawler/              # 수집기(general·youtube·naver·login_site·main_crawler·notifier)
├── shared/               # models · repository(local/firestore) · crypto · config · diagnostics
├── scripts/              # CLI(devserver · seed_sample · validate_setup)
├── data/                 # 로컬 모드 저장소(크롤러 로컬 실행용)
├── docs/                 # FeedWatch_클라우드_설치설명서.docx · SETUP_web.md · 개발계획서
├── firestore.rules       # 보안 규칙(멤버=CRUD, 관리자=사용자·설정, credentials 차단)
├── firebase.json·.firebaserc  # Firestore 규칙 + Hosting
├── .github/workflows/    # 크롤링 스케줄(06:00 / 18:00 KST)
└── legacy/v1.0_desktop/  # v1.0 데스크톱(CustomTkinter) + 빌드 산출물(dist) 보존본
```

---

## 4. 크롤러

새 글 수집은 Python 크롤러가 담당합니다. GitHub Actions가 하루 2회 자동 실행하며, 수동 실행도 가능합니다.

```powershell
# 전체 소스 크롤링(로컬에서 점검 시 .env에 FEEDWATCH_STORAGE=firestore 또는 local)
.\.venv\Scripts\python.exe -m crawler.main_crawler

# 특정 소스만 크롤링(문제 진단용)
.\.venv\Scripts\python.exe -m crawler.main_crawler --source src_xxxxx
```

- 신규 판단: `source_id + 제목 + URL` 해시로 중복 제거.
- 네트워크 오류는 **최대 3회 지수 백오프 재시도**.
- 사이트가 **연속 3회 실패**하면 관리자에게 이메일 경고를 보냅니다(소스 상태에 `연속실패` 표시).
- 새 글 이메일은 사용자별 발송 대기열에 먼저 저장합니다. SMTP가 일시적으로 실패하면 작업을 남겨
  다음 크롤링 실행에서 자동으로 다시 시도합니다.
- `app_config`(자동 보관일수·**휴지통 보관일수**·이메일 on/off)는 **웹 관리자 → 설정**에서 바꾸면 크롤러가 그대로 따릅니다.
- 이메일 **발송 방식**은 기본이 `자동`이라 크롤러 환경(`EMAIL_PROVIDER`/Secrets)을 따릅니다. 설정에서 특정 방식을
  고르면 그 값이 환경설정보다 우선합니다(예: `preview`로 두면 메일이 나가지 않습니다).

### GitHub Actions Secrets

| 이름 | 설명 |
|---|---|
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 JSON 전체 |
| `FEEDWATCH_ADMIN_EMAIL` | 기본 관리자 이메일(첫 실행 시드용) |
| `YOUTUBE_API_KEY` | (선택) 채널ID 자동추출이 실패할 때만 쓰는 폴백. 보통 불필요 |
| `FEEDWATCH_CRED_PASSPHRASE` | (로그인 사이트 또는 비공개 네이버 카페 사용 시) 웹에서 정한 ‘수집 비밀번호’ |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USERNAME` `SMTP_PASSWORD` `SMTP_FROM` | 이메일(SMTP) |

> 개별 사이트가 실패해도 워크플로는 성공으로 끝납니다(앱의 `연속실패` 표시와 관리자 메일로 알림).
> **모든** 사이트가 실패한 경우에만 빨간 X로 표시됩니다.

> 인트라넷(예: 사내망) 사이트는 GitHub Actions(외부망)에서 접근할 수 없습니다.
> 그런 소스는 내부망 PC에서 위 크롤러 명령을 직접/스케줄 실행하세요.

---

## 5. 소스 유형별 설정 (관리자 → URL 관리)

| 유형 | 방식 | 핵심 입력 |
|---|---|---|
| `general` | RSS 자동탐지 → 위치값 폴백 | **URL만 입력**(RSS/Atom 자동 감지). RSS가 없는 게시판이면 자세한 설정의 **‘글 목록 위치’** 가 필요하며, 비어 있으면 "RSS를 찾지 못했습니다" 실패로 표시됩니다 |
| `youtube` | 채널 RSS (API 키 불필요) | **채널 URL만 입력**(@핸들·/channel·/c·/user에서 채널ID 자동 추출). ‘채널 ID’ 칸은 자동 인식 실패 시에만 |
| `naver` | RSS 우선 → 쿠키 세션 | 블로그는 RSS 자동 추정. 카페는 ‘카페 본문 틀’ + ‘글 목록 위치’, 비공개면 ‘로그인 쿠키’ |
| `login_required` | Playwright | 아이디·비밀번호 입력칸/로그인 버튼 위치 + ‘글 목록 위치’ |

- **네이버 블로그**: `https://blog.naver.com/{id}` → `https://rss.blog.naver.com/{id}.xml` 자동 시도.
- **네이버 카페**: ‘카페 본문 틀’(기본 `iframe#cafe_main`)을 두고, 비공개 카페는 ‘로그인 쿠키’가 필요합니다.
  쿠키는 URL 설정에 평문으로 넣지 않고 관리자 전용 입력칸에서 암호화해 저장합니다.
- **로그인 사이트 자격증명**: 웹 관리자(관리자 권한)가 **URL 관리 화면에서 아이디/비밀번호를 직접 입력**합니다.
  최초 1회 **‘수집 비밀번호’**를 정하면 브라우저가 그 비밀번호로 **AES‑256 암호화(WebCrypto)** 해 저장하고,
  크롤러는 같은 값(`FEEDWATCH_CRED_PASSPHRASE`)으로 복호화합니다. 네이버 쿠키도 같은 방식이며,
  평문/암호화 키는 브라우저·DB에 남지 않습니다.
  - 크롤러 환경(.env / GitHub Secrets)에 **`FEEDWATCH_CRED_PASSPHRASE`** 를 ‘수집 비밀번호’와 동일하게 설정하세요.

브라우저는 보안정책(CORS)상 임의 사이트를 직접 가져올 수 없어, **‘위치’ 값 확인은 크롤러로** 합니다
(`--source`로 해당 소스만 돌려 로그를 확인).

---

## 6. 항목 상태 / 자동 보관

`신규(new)` → 읽음 `read` / 삭제 `deleted`, 그리고 **7일(설정값)** 미처리 시 `미처리 보관(archived_unread)`
으로 자동 이동합니다. 보관함은 `읽음/미처리`로 나눠 볼 수 있고, 휴지통에서 **복원·완전삭제**가 가능합니다.
자동 보관 기간은 웹 관리자 → 설정에서 변경합니다. 휴지통의 삭제 항목은 **휴지통 보관 기간(기본 30일)** 이 지나면
클라우드 크롤러 실행 시 영구 삭제됩니다(0으로 두면 자동 삭제하지 않음).

**알림 받을 사이트**는 프로필 → 내 설정에서 각자 고릅니다. **고른 사이트에서만** 메일이 오고,
아무것도 고르지 않으면 알림을 받지 않습니다(모두 받으려면 ‘전체 선택’). 대시보드 상단
**‘내 미확인’** 카드는 내가 **직전 방문 이후 새로 도착한**(내가 고른 사이트 기준) 글 수만 보여 줍니다.
목록의 새 글에는 `NEW` 표시가 붙고, 로그인할 때마다 “마지막으로 본 시점”이 갱신됩니다.

---

## 7. 보안 메모

- 보안 규칙([`firestore.rules`](firestore.rules)): 승인된 가족만 콘텐츠를 읽고 소스·구분값을 관리할 수 있으며,
  항목은 상태값만 변경할 수 있습니다. 전체 사용자 목록·사용자 관리·앱 설정은 **관리자만** 가능하고,
  `credentials`는 관리자가 암호화된 값만 쓸 수 있으며 클라이언트 읽기는 완전히 차단됩니다.
- 웹 클라이언트 설정(`apiKey` 등)은 비밀이 아닙니다(보안은 규칙+인증으로). `service_account.json`,
  `token.json`, `.env`, 쿠키 등 **민감 파일은 절대 깃에 올리지 마세요**(`.gitignore` 적용됨).

---

## 8. 운영 전 점검

[OPERATIONS_CHECKLIST.md](OPERATIONS_CHECKLIST.md) 를 순서대로 확인하세요.
