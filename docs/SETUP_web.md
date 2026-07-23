# FeedWatch v2 웹 설정 가이드 (비개발자용)

이 문서는 FeedWatch 웹 대시보드를 **데모로 체험**하고, **가족용 클라우드 운영**까지 올리는 과정을 차근차근 설명합니다.

---

## A. 먼저 데모로 체험하기 (5분, 설정 불필요)

1. 명령 프롬프트(또는 PowerShell)를 엽니다.
2. 아래를 입력합니다.

   ```powershell
   cd "D:\Users\vmfort\Desktop\개발\FeedWatch_v2"
   py scripts\devserver.py 5180 web
   ```

3. 브라우저에서 **http://localhost:5180** 접속.
4. 로그인 화면에서 `김우재(관리자)` 등을 골라 입장 → 신규/보관함/휴지통, 검색·필터, 관리자 화면을 둘러봅니다.
5. 오른쪽 위 화면 아이콘으로 **라이트/다크/시스템** 테마를 바꿀 수 있습니다.

> 데모의 모든 변경은 그 브라우저에만 저장됩니다. 관리자 → 설정 → **데모 데이터 초기화**로 되돌립니다.

---

## B. 클라우드(실제 운영) 올리기

가족이 각자 기기에서 같은 데이터를 실시간으로 보려면 Firebase가 필요합니다. 모두 **무료 한도**로 충분합니다.

### 1) Firebase 프로젝트

1. https://console.firebase.google.com → **프로젝트 추가**.
2. 좌측 **Firestore Database** → **데이터베이스 만들기** → 프로덕션 모드 → 위치 선택(asia-northeast3 권장).
3. 좌측 **Authentication** → 시작하기 → **이메일/비밀번호**와 **Google**을 사용 설정.

### 2) 웹 설정 파일 만들기

1. Firebase 콘솔 → 프로젝트 설정(톱니) → 일반 → "내 앱"에서 **웹 앱(</>)** 추가.
2. 표시되는 `firebaseConfig`의 값으로 **`web/firebase_config.json`** 파일을 만듭니다.
   (`web/firebase_config.example.json` 형식을 복사해서 채우면 됩니다.)

   ```json
   {
     "apiKey": "AIza...",
     "authDomain": "내프로젝트.firebaseapp.com",
     "projectId": "내프로젝트",
     "appId": "1:...:web:..."
   }
   ```

   > 이 값들은 비밀이 아닙니다(보안은 아래 규칙+로그인으로 보장). 그래도 깃에는 올리지 않습니다.

3. 이제 `py scripts\devserver.py 5180 web` 로 다시 열면 **클라우드 모드**로 동작합니다(로그인 화면이 이메일/Google로 바뀜).

### 3) 보안 규칙 배포 — 콘솔에 붙여넣기

Firebase CLI(=node/npm)를 설치하지 않아도 됩니다. 콘솔에서 바로 붙여넣는 게 더 빠릅니다.

1. 이 폴더의 [`firestore.rules`](../firestore.rules) 를 메모장으로 열어 **전체 복사**.
2. Firebase 콘솔 → **Firestore Database** → 상단 **규칙** 탭 → 기존 내용을 지우고 **붙여넣기** → **게시**.

> 규칙을 고칠 때마다 이 과정을 반복합니다. (CLI를 쓰고 싶다면 `firebase deploy --only firestore:rules`)

### 4) 첫 관리자 만들기 (한 번만)

사용자 문서는 **로그인 계정의 고유 ID(uid)** 로 저장되고, 보안 규칙이 그 uid로 관리자 여부를 확인합니다.
UID를 손으로 옮겨 적을 필요 없이 스크립트가 대신 찾아 줍니다.

1. 앱을 열고 **본인 Google(또는 이메일/비밀번호)로 로그인** → "승인 대기 중" 화면이 보입니다.
   (이 화면이 떠도 Auth 계정은 만들어진 상태입니다.)
2. Firebase 콘솔 → 프로젝트 설정 → **서비스 계정** → **새 비공개 키 생성** → 받은 JSON을 이 폴더에
   **`service_account.json`** 으로 저장합니다. (`.gitignore`에 있어 깃에 올라가지 않습니다)
3. 아래를 실행합니다.

   ```powershell
   cd "D:\Users\vmfort\Desktop\개발\FeedWatch_v2"
   py -m scripts.make_admin --list                 # 로그인된 계정 확인
   py -m scripts.make_admin --email 내이메일@gmail.com
   ```

4. 앱을 새로고침하면 관리자로 입장됩니다. 기본 구분값(공통·아빠·엄마)도 함께 만들어집니다.

이제부터 다른 가족은 **로그인 → 가입 신청** 하면 되고, 관리자가 **관리 → 가입 신청** 탭에서 **승인**하면
입장합니다. (이메일을 미리 등록하려면 **사용자 관리**에서 추가)

### 5) 어디서나 접속 — GitHub Pages 배포

Firebase Hosting은 CLI(node/npm)가 필요해서, **화면은 GitHub Pages로 올리고 DB·로그인만 Firebase를 씁니다.**
크롤러 때문에 어차피 GitHub 저장소가 필요하므로 한 저장소로 끝납니다.

1. GitHub에 **공개(Public) 저장소**를 만들고 이 폴더를 올립니다.
   (공개해도 됩니다 — 비밀값인 `.env`·`service_account.json`은 `.gitignore`로 빠지고, 웹 설정값은
   원래 공개되는 값입니다. 공개 저장소는 Actions도 무제한 무료입니다.)
2. 저장소 **Settings → Pages → Source** 를 **GitHub Actions** 로 지정합니다.
3. `web/firebase_config.json` 을 저장소에 함께 올리거나, 올리기 싫으면
   **Settings → Secrets and variables → Actions → Variables** 에 `FIREBASE_WEB_CONFIG` 라는 이름으로
   그 JSON 내용을 넣습니다. (둘 중 하나만 하면 됩니다)
4. Actions 탭 → **Deploy web app (GitHub Pages)** → Run workflow.
5. 나오는 주소(`https://<아이디>.github.io/<저장소이름>/`)를 **Firebase 콘솔 → Authentication → 설정 →
   승인된 도메인**에 `<아이디>.github.io` 로 추가합니다. ← **이걸 빠뜨리면 Google 로그인이 막힙니다.**

이제 그 주소를 가족과 공유하면 휴대폰에서도 바로 씁니다.

---

## C. 모니터링할 사이트 등록

웹 관리자 → **URL 관리**에서 추가합니다. 유형별 입력은 [README](../README.md#5-소스-유형별-설정-관리자--url-관리) 참고.
‘글 목록 위치’ 같은 값이 맞는지 확인하려면 크롤러를 해당 소스만 돌려 로그를 봅니다(아래 D).
구분값은 **여러 개 선택**할 수 있어, 한 사이트를 공통·아빠 양쪽에서 함께 볼 수 있습니다.

### 로그인 필요 사이트의 아이디/비밀번호

**웹 화면에서 바로 등록합니다**(관리자만 가능). URL 관리에서 유형을 `로그인 필요`로 고르면 아이디·비밀번호
칸이 나타납니다.

1. 아이디/비밀번호를 입력하고 저장하면 **‘수집 비밀번호’** 를 한 번 묻습니다(직접 정하는 값).
2. 브라우저가 그 비밀번호로 **AES‑256 암호화(WebCrypto)** 해서 저장합니다. 평문도, 암호화 키도 남지 않습니다.
3. 크롤러 환경(`.env` 또는 GitHub Secrets)에 **`FEEDWATCH_CRED_PASSPHRASE`** 를 **같은 값**으로 넣습니다.
   이 값이 없거나 다르면 복호화에 실패해 그 사이트만 수집되지 않습니다.

목록에는 "로그인정보 등록됨/미등록"으로 표시됩니다. 비밀번호를 바꾸려면 다시 입력해 저장하면 교체됩니다.

### 알림 받을 사이트 고르기

새 글 알림은 **사이트(URL) 단위**로 신청합니다. 각자 헤더 **프로필 → 내 설정**에서 "알림 받을 사이트"를
선택합니다. **고른 사이트에서만 알림이 옵니다** — 아무것도 고르지 않으면 알림을 받지 않습니다.
모두 받고 싶으면 **‘전체 선택’** 버튼을 누르세요. 관리자는 **사용자 관리 → 편집**에서 대신 설정할 수도 있습니다.
새 가족이 승인되면 처음에는 아무것도 선택돼 있지 않으니, 각자 한 번씩 골라야 알림이 옵니다
(대시보드에 안내가 뜹니다).
메일에는 "[사이트명] 새 글 N건"과 글 제목·링크가 담깁니다. 발송 계정(SMTP/Gmail)은 크롤러 환경에서 설정합니다.

---

## D. 크롤러 자동화

새 글 수집은 Python 크롤러가 합니다.

### 로컬에서 1회 실행/점검

```powershell
cd "D:\Users\vmfort\Desktop\개발\FeedWatch_v2"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium    # 로그인 사이트를 쓸 때만

# .env (env 예시는 .env.example)
#   FEEDWATCH_STORAGE=firestore
#   FIREBASE_PROJECT_ID=내프로젝트
#   GOOGLE_APPLICATION_CREDENTIALS=service_account.json   ← 콘솔→프로젝트설정→서비스계정에서 받은 키
#   EMAIL_PROVIDER=smtp  (+ SMTP_* 값)    ← 메일을 실제로 보낼 때
#   FEEDWATCH_CRED_PASSPHRASE=수집비밀번호  ← 로그인 필요 사이트가 있을 때만
.\.venv\Scripts\python.exe .\scripts\validate_setup.py                 # 환경 점검
.\.venv\Scripts\python.exe -m crawler.main_crawler
.\.venv\Scripts\python.exe -m crawler.main_crawler --source src_xxxx   # 특정 소스만
```

### GitHub Actions 자동 실행(하루 2회)

저장소 Secrets에 [README의 표](../README.md#github-actions-secrets) 값을 등록하면 06:00/18:00(KST)에 자동 실행됩니다.
수동 실행은 Actions 탭 → **FeedWatch Crawl** → Run workflow.

> 사내망/인트라넷 사이트는 외부망 Actions에서 접근 불가 → 내부망 PC에서 위 로컬 명령을 사용하세요.

---

## 자주 막히는 곳

- **로그인이 안 돼요**: 로그인하려는 이메일이 `users` 목록에 있나요? 관리자가 먼저 등록해야 합니다.
- **화면이 비어 있어요**: Firestore 규칙을 배포했는지, 로그인 상태인지 확인하세요(규칙상 로그인해야 읽힙니다).
- **`index.html` 더블클릭 시 안 떠요**: ES 모듈은 `file://`에서 막힙니다. 반드시 로컬 서버(위 명령)로 여세요.
- **새 글이 안 들어와요**: 크롤러를 `--source`로 돌려 로그(관리 → 크롤링 로그)의 실패 메시지를 확인하세요.
  "RSS 피드를 찾지 못했습니다"라고 나오면 그 사이트는 **자세한 설정의 ‘글 목록 위치’** 가 필요합니다.
- **메일이 안 와요**: ① 설정 → 이메일 발송 방식이 `preview`면 발송하지 않습니다(`자동` 권장).
  ② 내 설정 → 알림 받을 사이트가 그 사이트를 포함하는지, ③ Secrets의 `SMTP_*`가 맞는지 확인하세요.
