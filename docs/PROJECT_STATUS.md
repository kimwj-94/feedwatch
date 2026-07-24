# FeedWatch 개발 이력 · 현재 상태 · 남은 절차

> 다른 PC에서 이어서 작업하기 위한 인수인계 문서입니다.
> 최종 갱신: **2026-07-24**
> 개인정보(관리자 이메일·UID·비밀값)는 이 문서에 넣지 않습니다 — 공개 저장소이기 때문입니다.
> 그 값들은 별도 `이어받기` 묶음(로컬 zip)에 있습니다.

---

## 1. 목표

여러 웹사이트(일반 공지·유튜브·네이버 카페/블로그·로그인 필요 사이트)의 **새 글을 자동으로 모아**,
**가족이 하나의 대시보드에서 확인**하고 **이메일로 알림**받는 개인용 모니터링 시스템.

핵심 제약 두 가지:
- **상시 켜 두는 PC가 없어야 한다** → 수집은 클라우드(GitHub Actions), 화면은 정적 호스팅
- **무료로 운영되어야 한다** → Firebase 무료(Spark) + GitHub 무료 한도 안에서 동작

## 2. 구조

| 조각 | 실체 | 어디서 도나 |
|---|---|---|
| 화면 | `web/` — 빌드 도구 없는 정적 웹앱(ES 모듈) | GitHub Pages |
| 데이터·로그인 | Firestore + Firebase Auth | 구글 클라우드 |
| 수집기 | `crawler/` — Python | GitHub Actions cron (하루 2회, 06:00·18:00 KST) |

- 앱은 `web/firebase_config.json` **유무로 모드를 자동 판별**합니다.
  있으면 **CLOUD**(실제 운영), 없으면 **DEMO**(키 없이 샘플 데이터로 전 기능 체험).
- 데이터 접근은 `web/js/data/adapter.js` 계약을 `local.js`(데모)·`firestore.js`(클라우드)가
  똑같이 구현합니다. 화면 코드는 백엔드를 모릅니다.
- Python도 같은 구조로 `shared/repository.py`(로컬 JSON) ↔ `shared/firestore_repository.py`.

## 3. 지금까지 완료된 것

**클라우드 구성 (완료)**
- [x] Firebase 프로젝트 생성 (Spark 무료 요금제, 카드 미등록)
- [x] Firestore 생성 — `(default)` DB, 리전 `asia-northeast3`(서울), 프로덕션 모드
- [x] Authentication — 이메일/비밀번호 + Google 사용 설정
- [x] 보안 규칙 게시 (`firestore.rules` 를 콘솔 규칙 탭에 붙여넣기)
- [x] 첫 관리자 등록 (콘솔에서 `users/{uid}` 문서 수동 생성)
- [x] GitHub 공개 저장소 생성 + 푸시
- [x] GitHub Pages 배포 (`Deploy web app` 워크플로, Source = GitHub Actions)
- [x] 저장소 변수 `FIREBASE_WEB_CONFIG` 등록 (배포 시 설정 파일 주입)
- [x] Authentication → 승인된 도메인에 Pages 도메인 추가
- [x] 구분값 생성 및 동작 확인

자동 수집·배포·실제 Gmail 발송까지 정상 운영을 확인했습니다. 가족별 알림 선택 등 사용자 운영 항목은 아래 5장 참고.

## 4. 오늘(2026-07-23) 작업 이력

### 4-1. 클라우드에서 터졌을 버그 (배포 전 발견·수정)

| 문제 | 원인 | 조치 |
|---|---|---|
| **수집이 통째로 멈춤** | 웹이 저장한 `colorIndex` 같은 미지 필드를 Python이 그대로 언패킹해 TypeError → `list_groups()`에서 죽음 | `FirestoreRepository`가 `from_dict()`로 모르는 키를 무시하도록 변경 + 필드명을 snake_case로 통일 |
| **메일이 조용히 안 나감** | `app_config.email_provider` 기본값 `preview`가 Actions의 SMTP 설정을 덮어씀 | 기본값을 `''`(=크롤러 환경설정 따름)로 변경, 설정 UI에 '자동' 옵션 추가 |
| **가입 신청 중복 누적** | 승인 대기자는 목록을 못 읽어(규칙) 중복 검사가 항상 실패 | 문서 ID를 `req_<uid>`로 고정 |
| **관리자 권한이 자꾸 풀림** | 자기 가입신청 승인 → `role`을 member로 덮어씀 → 강등 직후 신청 삭제까지 규칙에 막혀 실패 → 반복 | 이미 등록된 계정이면 role을 건드리지 않음. 등록된 사람의 신청은 '대기'로 세지 않음 |
| **프로필 저장이 role을 지움** | 사용자 문서를 merge 없이 통째로 덮어씀. 규칙상 관리자는 이 쓰기가 허용돼 **관리자만** 피해 | `updateProfile`이 허용 필드만 merge, `saveUser`도 merge |
| **피드 오염** | 선택자가 없으면 페이지의 모든 링크를 글로 수집 | 명확한 실패로 전환(연속실패 표시·관리자 메일) |

### 4-2. 디자인 개편 후 회귀 (사용자 CSS 수정분 점검)

`.checkset`·`.dstat-line`·`.notice`·모바일 미디어쿼리가 삭제돼 있던 것을 복원.
대시보드가 휴대폰에서 화면 밖으로 넘치던 문제(375px에 864px 렌더), 사이드바가 750px로
커져 짧은 화면에서 프로필·로그아웃이 잘리던 문제, 목록 갱신마다 전체가 깜빡이던 문제 수정.
Google 로그인 버튼의 G 마크가 카드를 덮을 만큼 커지던 **원래 있던 버그**도 함께 수정.

### 4-3. 이메일 알림 실동작 검증 (가짜 SMTP 서버로 전 과정 실행)

발송을 한 번도 실제로 돌려본 적이 없어 검증했더니, **새 글은 정상 수집되는데 메일은 한 통도
나가지 않고** 조용히 미리보기 파일로만 빠지고 있었습니다. 원인 둘을 고쳤습니다.

- `_send_smtp`가 **무조건 `starttls()`** 를 호출 → STARTTLS 미지원 서버나 **465(SMTPS)** 에서는
  항상 실패. → 465는 `SMTP_SSL`, 그 외에는 서버가 지원을 광고할 때만 승격. timeout 30초 추가
- `_send`가 **예외를 통째로 삼켜** 실패 이유를 알 수 없었음(Actions에서는 미리보기 파일마저
  버려져 흔적 0). → 실패 사유를 콘솔과 앱 **크롤링 로그**에 그대로 표시

검증한 시나리오: 새 글 2건 → 구독자에게만 1통(제목·본문·구분값 라벨 정확) / 미구독·미선택자에게는
발송 안 됨 / 재실행 시 중복 발송 없음 / 게시물 1건 추가 → 그 1건만 담긴 메일 1통 /
SMTP 실패 시 사유 노출.

실제 Gmail 앱 비밀번호를 GitHub Secret에 등록한 뒤 일회성 알림 작업을 넣어 운영 환경에서도 검증했습니다.
GitHub Actions에서 SMTP 인증·발송이 성공했고, 성공한 알림 작업이 Firestore 대기열에서 자동 삭제되는 것까지 확인했습니다.

### 4-4. 기능 추가

- **구분값 복수 지정** — `group_id`(1개) → `group_ids`(여러 개). 한 사이트를 공통+아빠 양쪽에 넣을 수 있음
- **구분값 색 직접 선택** — 빨주노초파남보+회색. 자동 배정은 파랑→초록→보라 순(빨강은 맨 뒤)
- **고급 설정을 일반인 말로** — "메타 JSON"·"선택자(CSS)" → 유형별 이름 붙은 입력칸 + 찾는 법 안내
- **알림 대상 명시 선택** — 미선택 = 알림 없음(예전엔 미선택 = 전체). '전체 선택' 버튼 제공
- **접근성** — 보조 텍스트 대비 2.56:1 → 4.76:1, 구분값 8색 모두 WCAG AA 통과
- **외부 폰트 의존 제거** — Google Fonts `@import` 삭제(사내망 차단 시 렌더 지연 방지)

### 4-5. 운영 안정화·보안 보강 (2026-07-24)

- **회귀 테스트 도입** — Python 표준 `unittest` 기반 19개 테스트와 GitHub Actions `Test` 워크플로 추가.
  해시 판정·과거 스키마·첫 수집·중복 제거·알림 필터·메일 재시도·암호화 쿠키·자격증명 정리를 검증
- **UID 기반 가입으로 통일** — 이메일 사전 등록은 Firestore UID 권한과 맞지 않아 제거.
  가족이 먼저 로그인해 가입 신청을 만들고 관리자가 승인하는 흐름만 사용
- **사용자 정보 노출 축소** — 일반 구성원은 `users/{본인 uid}`만 읽고,
  전체 사용자 목록과 가입 신청 실시간 구독은 관리자만 수행
- **이메일 재시도 대기열** — 사용자별 발송 작업을 `notification_jobs`에 먼저 저장하고,
  성공할 때만 제거. SMTP 일시 실패 시 다음 크롤링 실행에서 자동 재시도
- **수집 저장 안정화** — 같은 실행 안의 중복도 제거, Firestore 450건 단위 분할 저장,
  항목 저장 성공 뒤에만 첫 수집 완료 표시
- **중복 실행 방지** — GitHub Actions 크롤러에 concurrency 그룹 추가
- **관리자 실패 알림 수정** — 첫 관리자에게 성공하면 멈추던 문제를 고쳐 관리자 전원에게 발송
- **자격증명 수명주기 정리** — 로그인정보 연결 사이트 삭제 시 자격증명도 원자적으로 삭제,
  아이디·비밀번호 한쪽만 입력한 덮어쓰기 차단, 수집 비밀번호를 브라우저 저장소가 아닌 화면 메모리에만 유지
- **네이버 쿠키 암호화** — 비공개 카페 쿠키를 평문 `metadata` 대신 AES-256-GCM 암호화
  `credentials`에 저장. 기존 평문 데이터는 크롤러 호환을 유지하며 다음 편집 시 암호화 이전 요구
- **데모 서버 노출 차단** — 개발용 서버를 `127.0.0.1`에만 바인딩
- **JavaScript 동적 게시판 지원** — 정적 HTML에 글이 없고 `metadata.render_js`가 켜진 일반 사이트는
  Playwright로 렌더링한 뒤 선택자를 적용. 청년안심주택 모집공고에서 실제 수집 검증

검증 결과:
- Python 3.13 환경 진단: **FAIL 0**
- Python 회귀 테스트: **19/19 통과**
- 전체 웹 JavaScript 구문 검사: **통과**
- localhost 데모 응답: HTML·JS·CSS·샘플 JSON 모두 200, `firebase_config.json` 미존재 시 DEMO 모드 확인
- Word 설치설명서 재생성 및 DOCX ZIP·XML 구조 검증 통과. 이 PC에 LibreOffice가 없어 페이지 이미지 렌더 검증은 생략
- Firebase CLI로 `firestore.rules` 컴파일 및 실제 프로젝트 게시 성공
- GitHub Pages 배포 성공, 공개 주소의 HTML·CSS·JavaScript·Firebase 설정 모두 HTTP 200 확인
- 실제 GitHub Crawl: 3개 소스 모두 성공, 첫 수집 28건 저장(기존 글이므로 메일 제외), 재실행 신규 0건
- 실제 Gmail SMTP 테스트 메일 발송 및 알림 작업 자동 삭제 확인

> 브라우저 자동 클릭 검증은 현재 Codex 브라우저 연결의 로컬 권한 오류로 실행하지 못했습니다.
> 정적 응답·구문·단위 테스트는 모두 통과했으며, 실제 브라우저 수동 점검은 아래 5장 운영 준비 때 함께 진행합니다.

## 5. 남은 운영 절차

### 5-1. 크롤러 자동화 (완료)

GitHub 저장소 **Settings → Secrets and variables → Actions → Secrets** 에 등록:

| Secret | 값 | 상태 |
|---|---|---|
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID | ✅ 등록됨 |
| `FEEDWATCH_ADMIN_EMAIL` | 관리자 이메일 | ✅ 등록됨 |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USERNAME` `SMTP_FROM` | Gmail 기준 값 | ✅ 등록됨 |
| **`SMTP_PASSWORD`** | Google 계정 **앱 비밀번호 16자리** | ✅ 등록·실제 발송 확인 |
| **`FIREBASE_SERVICE_ACCOUNT_JSON`** | 콘솔 → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 → **JSON 내용 전체** | ✅ 등록·실제 Firestore 연결 확인 |
| `FEEDWATCH_CRED_PASSPHRASE` | (로그인 필요 사이트를 쓸 때만) 웹에서 정한 '수집 비밀번호' | ⬜ 해당 시 |

> **앱 비밀번호**는 일반 로그인 비밀번호와 다릅니다. Google 계정 비밀번호를 바꾸면 기존 앱 비밀번호가
> 폐기될 수 있으므로, 메일 인증 오류가 나면 새 앱 비밀번호를 만들어 `SMTP_PASSWORD`를 갱신하세요.
> 다른 메일을 쓰려면 `SMTP_HOST`·`SMTP_PORT`·`SMTP_USERNAME`·`SMTP_FROM`도 함께 바꾸세요
> (네이버 = `smtp.naver.com` / `465`, 메일 설정에서 SMTP 사용을 먼저 켜야 함).

수동 점검은 **Actions → FeedWatch Crawl → Run workflow** 로 실행합니다.

> **메일이 안 오면 앱의 관리 → 크롤링 로그를 보세요.** 이제 `[이메일]` 줄에 실패 사유가
> 그대로 남습니다(인증 실패, 연결 거부 등). Gmail은 일반 비밀번호가 아니라 **앱 비밀번호**를
> 써야 하고, 2단계 인증이 켜져 있어야 발급됩니다. 포트는 587(STARTTLS) 또는 465(SSL) 둘 다 됩니다.

### 5-2. 실제 운영 준비

- [x] 초기 감시 사이트 3개 등록 및 실제 수집 확인
- [ ] 각자 **내 설정 → 알림 받을 사이트** 선택 (안 고르면 메일이 오지 않습니다)
- [ ] 가족 초대: 앱 주소 공유 → 각자 로그인 → 관리자가 **관리 → 가입 신청**에서 승인
- [x] Gmail SMTP 테스트 메일 실제 발송 확인

### 5-3. 로컬에서 점검하고 싶을 때

```powershell
git clone https://github.com/kimwj-94/feedwatch.git
cd feedwatch
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 이어받기 묶음의 firebase_config.json 을 web\ 에 복사
# 이어받기 묶음의 .env 를 프로젝트 루트에 복사 후 SMTP 값 채우기
# service_account.json 은 Firebase 콘솔에서 새로 발급

.\.venv\Scripts\python.exe .\scripts\validate_setup.py          # 환경 점검
.\.venv\Scripts\python.exe -m crawler.main_crawler              # 전체 수집
.\.venv\Scripts\python.exe -m crawler.main_crawler --source src_xxxx   # 특정 사이트만
```

데모(설정 없이 체험)는 `py scripts\devserver.py 5180 web` 후 `http://localhost:5180`.

## 6. 결정 사항과 이유 (검토 기록)

| 결정 | 이유 |
|---|---|
| **Firebase Hosting 대신 GitHub Pages** | 작업 PC에 node/npm이 없어 Firebase CLI 설치 불가. 크롤러 때문에 어차피 GitHub 저장소가 필요해 한 곳으로 통합 |
| **보안 규칙은 저장소에서 관리** | `firestore.rules`를 Git으로 추적하고 Firebase CLI로 컴파일·게시까지 검증 |
| **저장소를 공개(Public)로** | Pages·Actions 무료 한도가 공개 저장소에서 넉넉함. 비밀값은 전부 `.gitignore`+Secrets로 분리 |
| **웹 설정을 저장소 변수로 주입** | `firebase_config.json`을 커밋하지 않으면서 배포는 되게. 값 자체는 비밀이 아님 |
| **알림: 미선택 = 안 받음** | "비워두면 전체"는 원치 않는 알림을 받게 되는 위험한 기본값 |
| **선택자 없으면 수집 실패 처리** | 예전엔 페이지의 모든 링크를 글로 넣어 피드가 오염됐고, 해시 중복제거 때문에 되돌리기 어려움 |
| **개별 사이트 실패는 워크플로 성공** | 매번 빨간 X가 뜨면 진짜 장애를 놓침. 전부 실패한 경우만 실패 처리 |
| **서비스 계정 키는 회사 PC에 두지 않음** | 프로젝트 전체 권한을 가진 키. Actions는 Secrets로 받으므로 파일이 필요 없음 |

## 7. 알려진 한계 / 나중에 볼 것

- **인트라넷(사내망) 사이트는 GitHub Actions에서 접근 불가** → 그런 사이트만 내부망 PC에서
  크롤러를 직접·예약 실행해야 합니다
- **새 사이트를 추가해도 기존 구성원은 자동 구독되지 않습니다**(명시 선택 방식의 결과).
  원하면 "새 사이트 자동 포함" 옵션을 추가할 수 있습니다
- **새 글 판별은 지문(해시) 대조**입니다 — 기준은 `사이트ID + (피드 고유ID > 주소 > 제목)`.
  날짜를 보지 않으므로 사이트가 날짜를 안 줘도 동작하지만, **게시판 주소 체계가 개편되면**
  기존 글이 대량 재알림될 수 있습니다. 그럴 땐 해당 사이트를 지웠다 다시 등록하면
  첫 수집으로 취급돼 알림 없이 재수집됩니다
- **한 번에 보는 목록 상한**: 일반·네이버 30건, 유튜브 15건. 하루 2회 수집 사이에
  이보다 많은 글이 올라오는 사이트는 놓칠 수 있습니다(고급 설정에서 조정 가능)
- **Firestore 읽기 비용** — 크롤 1회당 `items` 전체를 3번 읽습니다(중복제거·자동보관·휴지통정리).
  가족 규모에서는 무료 한도 안이지만, 글이 수천 건 쌓이면 손볼 지점입니다
- **`crawl_logs`가 무한 누적**됩니다. 90일 정리 같은 게 있으면 좋습니다
- **서비스 워커가 없어** 오프라인은 지원하지 않습니다(설치는 됩니다).
  Firestore가 필요한 앱이라 우선순위는 낮습니다
- 콘솔 UI가 자주 바뀝니다. 메뉴를 못 찾으면 콘솔 맨 위 **제품 검색**을 쓰세요

## 8. 참고 문서

- [README.md](../README.md) — 전체 개요·소스 유형별 설정·Secrets 표
- [docs/SETUP_web.md](SETUP_web.md) — 비개발자용 단계별 설치
- [docs/FeedWatch_클라우드_설치설명서.docx](FeedWatch_클라우드_설치설명서.docx) — 그림 자리 포함 Word판
- [OPERATIONS_CHECKLIST.md](../OPERATIONS_CHECKLIST.md) — 운영 전 점검표
