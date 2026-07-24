# -*- coding: utf-8 -*-
"""의존성 없이(zipfile + 표준 라이브러리) FeedWatch 클라우드 설치 설명서 .docx 생성.
실행: python docs/_build_setup_doc.py  → docs/FeedWatch_클라우드_설치설명서.docx
"""
from __future__ import annotations
import zipfile
from xml.dom import minidom
from pathlib import Path

OUT = Path(__file__).resolve().parent / "FeedWatch_클라우드_설치설명서.docx"

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------------- 문서 빌더 ----------------
class Doc:
    def __init__(self):
        self.body: list[str] = []
        self.nums: list[int] = []   # 십진(번호) 목록 인스턴스용 abstractNum=1 참조
        self._numid = 2             # 1은 불릿(abstract 0). 2부터 번호목록.

    def _run(self, text, *, b=False, i=False, mono=False, color=None, sz=None):
        rpr = []
        if mono: rpr.append('<w:rStyle w:val="Mono"/>')
        if b: rpr.append("<w:b/>")
        if i: rpr.append("<w:i/>")
        if color: rpr.append(f'<w:color w:val="{color}"/>')
        if sz: rpr.append(f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>')
        rprx = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""
        return f'<w:r>{rprx}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'

    def para(self, runs, *, style=None, spacing_after=None):
        ppr = []
        if style: ppr.append(f'<w:pStyle w:val="{style}"/>')
        if spacing_after is not None: ppr.append(f'<w:spacing w:after="{spacing_after}"/>')
        pprx = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
        rx = "".join(runs) if isinstance(runs, list) else runs
        self.body.append(f"<w:p>{pprx}{rx}</w:p>")

    def h(self, text, lvl=1):
        self.para([self._run(text)], style=f"Heading{lvl}")

    def title(self, text): self.para([self._run(text)], style="DocTitle")
    def subtitle(self, text): self.para([self._run(text)], style="DocSub")

    def p(self, text):
        if isinstance(text, list): self.para(text)
        else: self.para([self._run(text)])

    def bullet(self, text):
        runs = text if isinstance(text, list) else [self._run(text)]
        self.body.append(f'<w:p><w:pPr><w:pStyle w:val="ListB"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>{"".join(runs)}</w:p>')

    def steps(self, items):
        nid = self._numid; self._numid += 1; self.nums.append(nid)
        for it in items:
            runs = it if isinstance(it, list) else [self._run(it)]
            self.body.append(f'<w:p><w:pPr><w:pStyle w:val="ListN"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{nid}"/></w:numPr></w:pPr>{"".join(runs)}</w:p>')

    def callout(self, text, kind="tip"):
        style = "CalloutWarn" if kind == "warn" else "Callout"
        label = "⚠️ 주의  " if kind == "warn" else ("💡 팁  " if kind == "tip" else "ℹ️ 참고  ")
        self.para([self._run(label, b=True), self._run(text)], style=style)

    def code(self, lines):
        runs = []
        for idx, ln in enumerate(lines):
            if idx: runs.append("<w:r><w:br/></w:r>")
            runs.append(f'<w:r><w:t xml:space="preserve">{esc(ln)}</w:t></w:r>')
        self.body.append(f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>{"".join(runs)}</w:p>')

    def shot(self, text):
        self.para([self._run("📷 화면  ", b=True, color="2E6BD6"), self._run(text, i=True, color="6B7280")], style="Shot")

    def spacer(self): self.para([], spacing_after=60)

    def table(self, headers, rows, widths):
        total = sum(widths)
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
        def cell(text, w, *, head=False, bullets=False):
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="EEF1F6"/>' if head else ""
            paras = ""
            lines = text if isinstance(text, list) else [text]
            for ln in lines:
                rpr = "<w:rPr><w:b/></w:rPr>" if head else ""
                paras += f'<w:p><w:pPr><w:spacing w:after="0"/><w:pStyle w:val="Cell"/></w:pPr><w:r>{rpr}<w:t xml:space="preserve">{esc(ln)}</w:t></w:r></w:p>'
            return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shade}'
                    f'<w:tcMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar>'
                    f'<w:vAlign w:val="center"/></w:tcPr>{paras}</w:tc>')
        rows_xml = ""
        rows_xml += "<w:tr>" + "".join(cell(h, widths[i], head=True) for i, h in enumerate(headers)) + "</w:tr>"
        for r in rows:
            rows_xml += "<w:tr>" + "".join(cell(c, widths[i]) for i, c in enumerate(r)) + "</w:tr>"
        b = '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="D6DBE5"/><w:left w:val="single" w:sz="4" w:color="D6DBE5"/><w:bottom w:val="single" w:sz="4" w:color="D6DBE5"/><w:right w:val="single" w:sz="4" w:color="D6DBE5"/><w:insideH w:val="single" w:sz="4" w:color="D6DBE5"/><w:insideV w:val="single" w:sz="4" w:color="D6DBE5"/></w:tblBorders>'
        self.body.append(f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>{b}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rows_xml}</w:tbl>')
        self.spacer()

    def pagebreak(self):
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

# ---------------- 콘텐츠 작성 ----------------
d = Doc()
R = d._run

d.title("FeedWatch 클라우드 설치·설정 설명서")
d.subtitle("Firebase(Firestore) + GitHub로 가족이 함께 쓰기 · 처음 하는 분을 위한 단계별 안내")
d.subtitle("문서 버전 1.0 · 2026-06")
d.spacer()

d.callout("이 설명서대로 따라 하면, 가족 누구나 인터넷만 있으면 휴대폰·PC에서 FeedWatch에 접속해 새 글을 확인하고 사이트를 추가·수정·삭제할 수 있습니다. 따로 켜 둬야 하는 '메인 PC'는 없습니다. 새 글 자동 수집(크롤러)은 GitHub의 무료 서버에서 하루 2번 알아서 돕니다.", "tip")
d.spacer()

d.h("0. 5분 요약 — 큰 그림", 1)
d.p("FeedWatch는 세 조각으로 동작합니다. 이 설명서는 이 셋을 차례로 연결합니다.")
d.table(
    ["조각", "무엇인가", "어디서 도나"],
    [
        ["웹앱(화면)", "가족이 브라우저로 여는 대시보드. 새 글 보기·사이트 추가/수정/삭제.", "정적 파일(호스팅) — PC 불필요"],
        ["Firestore", "구글이 운영하는 클라우드 데이터베이스. 사이트·글·사용자·설정을 한곳에 저장하고 가족 간 실시간 공유.", "구글 클라우드 — PC 불필요"],
        ["크롤러", "등록한 사이트를 돌며 새 글을 모아 Firestore에 넣고 메일 알림을 보냄.", "GitHub Actions(무료) — 하루 2회 자동"],
    ],
    [1600, 4626, 2800],
)
d.p([R("준비 시간은 약 ", ), R("30~40분", b=True), R(" 입니다. 한 번만 설정하면 그 뒤로는 신경 쓸 일이 거의 없습니다.")])
d.callout("이 모든 서비스는 가족 규모에서는 전부 '무료 한도' 안에서 돌아갑니다(13장 참고).", "note")

d.pagebreak()
d.h("1. 먼저 알아두기 — 용어", 1)
d.p("처음 보는 단어가 많을 수 있습니다. 아래만 알면 충분합니다.")
d.table(
    ["용어", "쉽게 말하면"],
    [
        ["Google / 구글 계정", "Gmail 주소. Firebase·GitHub 모두 구글 계정으로 시작합니다."],
        ["Firebase", "구글이 만든 '앱 뒷단 세트'. 이 안에 Firestore·로그인·호스팅이 들어 있습니다."],
        ["Firestore", "클라우드 데이터베이스(자료 보관함). 사이트·글·사용자 정보가 여기 저장됩니다."],
        ["Authentication(인증)", "로그인 기능. 구글 로그인·이메일/비밀번호 로그인을 켭니다."],
        ["Hosting(호스팅)", "웹앱을 인터넷 주소로 띄워, 어느 기기서나 열 수 있게 해 줍니다.(선택)"],
        ["보안 규칙", "'누가 무엇을 읽고 쓸 수 있는지' 정하는 규칙 파일. 가족만 접근하도록 막아 줍니다."],
        ["GitHub", "코드 저장소. 여기에 FeedWatch를 올리면 자동 수집(Actions)을 쓸 수 있습니다."],
        ["GitHub Actions", "정해진 시간에 자동으로 프로그램을 돌려 주는 무료 기능. 크롤러를 하루 2번 실행합니다."],
        ["크롤러", "사이트를 방문해 새 글을 모아 오는 수집 프로그램(파이썬)."],
        ["UID", "로그인 계정마다 부여되는 고유 번호. 7장에서 make_admin 명령이 자동으로 찾아 씁니다."],
    ],
    [2000, 7026],
)

d.h("2. 준비물", 1)
d.bullet([R("구글 계정", b=True), R(" (Gmail) — 관리자(대표) 1개. 가족 각자도 구글 또는 이메일로 로그인합니다.")])
d.bullet("크롬(Chrome) 같은 최신 브라우저")
d.bullet("인터넷 연결")
d.bullet([R("(크롤러 자동화를 쓰려면) ", ), R("GitHub 계정", b=True), R(" — 없으면 9장에서 무료로 만듭니다.")])
d.callout("회사·병원 인트라넷처럼 외부에서 접속이 막힌 사이트는 GitHub 서버가 들어갈 수 없습니다. 그런 사이트는 내부망 PC에서 크롤러를 직접 돌려야 합니다(9장 끝 참고).", "warn")

d.pagebreak()
d.h("3. STEP 1 — Firebase 프로젝트 만들기", 1)
d.steps([
    [R("브라우저에서 "), R("https://console.firebase.google.com", mono=True), R(" 접속 → 구글 계정으로 로그인.")],
    [R("‘프로젝트 만들기(Create a project)’ 클릭.")],
    [R("프로젝트 이름 입력(예: "), R("feedwatch-가족", mono=True), R("). 아무 이름이나 가능합니다.")],
    [R("Google 애널리틱스는 "), R("사용 안 함(Disable)", b=True), R("으로 둬도 됩니다 → ‘만들기’.")],
    [R("1분쯤 기다리면 프로젝트가 생성됩니다 → ‘계속’.")],
])
d.shot("Firebase 콘솔의 프로젝트 만들기 화면")

d.h("4. STEP 2 — Firestore 데이터베이스 만들기", 1)
d.steps([
    [R("왼쪽 메뉴에서 "), R("빌드 → Firestore Database", b=True), R(" 클릭.")],
    [R("‘데이터베이스 만들기’ 클릭.")],
    [R("위치는 "), R("asia-northeast3 (서울)", b=True), R(" 권장 → 다음.")],
    [R("시작 모드는 "), R("프로덕션 모드", b=True), R(" 선택(나중에 6장에서 보안 규칙을 올립니다) → 사용 설정.")],
])
d.callout("프로덕션 모드로 시작하면 처음엔 아무도 접근 못 하는 상태입니다. 정상입니다 — 6장에서 가족만 접근하도록 규칙을 올립니다.", "note")

d.h("5. STEP 3 — 로그인(Authentication) 켜기", 1)
d.steps([
    [R("왼쪽 메뉴 "), R("빌드 → Authentication", b=True), R(" → ‘시작하기’.")],
    [R("‘Sign-in method(로그인 방법)’ 탭에서 "), R("이메일/비밀번호", b=True), R(" 를 사용 설정.")],
    [R("같은 화면에서 "), R("Google", b=True), R(" 도 사용 설정(지원 이메일 선택 후 저장).")],
])
d.p("이제 가족은 구글 또는 이메일/비밀번호로 로그인할 수 있습니다(실제 입장 허용은 7·10장에서).")

d.pagebreak()
d.h("6. STEP 4 — 웹앱 설정값 받아 firebase_config.json 만들기", 1)
d.steps([
    [R("Firebase 콘솔 왼쪽 위 "), R("톱니바퀴 → 프로젝트 설정", b=True), R(".")],
    [R("‘내 앱’ 섹션에서 "), R("</> (웹)", b=True), R(" 아이콘 클릭 → 앱 닉네임 입력(예: feedwatch-web) → ‘앱 등록’.")],
    [R("화면에 나오는 "), R("firebaseConfig", mono=True), R(" 값(apiKey 등)을 확인합니다.")],
    [R("FeedWatch 폴더의 "), R("web/firebase_config.example.json", mono=True), R(" 을 복사해 "), R("web/firebase_config.json", mono=True), R(" 파일을 만들고, 아래처럼 값을 채웁니다.")],
])
d.code([
    "{",
    '  "apiKey": "AIza...(콘솔의 값)",',
    '  "authDomain": "내프로젝트.firebaseapp.com",',
    '  "projectId": "내프로젝트",',
    '  "appId": "1:...:web:..."',
    "}",
])
d.callout("이 값들은 비밀번호가 아닙니다. 노출돼도 안전합니다(보안은 6장 규칙 + 로그인으로 지킵니다). 그래도 깃에는 올리지 않도록 .gitignore에 이미 등록돼 있습니다.", "note")

d.h("7. STEP 5 — 데모로 먼저 확인", 1)
d.p("설정이 맞는지 가볍게 확인합니다.")
d.steps([
    [R("FeedWatch 폴더의 "), R("FeedWatch_데모실행.bat", b=True), R(" 더블클릭 → 브라우저가 열립니다.")],
    [R("로그인 화면이 "), R("이메일·Google 로그인", b=True), R(" 모양이면 클라우드 모드로 잘 연결된 것입니다.")],
    [R("(예전 사용자-선택 화면이 보이면 "), R("web/firebase_config.json", mono=True), R(" 위치/내용을 다시 확인하세요.)")],
])

d.h("8. STEP 6 — 보안 규칙 올리기", 1)
d.p("‘가족만 접근’ 규칙을 Firestore에 적용합니다. 두 방법 중 하나를 쓰면 됩니다.")
d.h("방법 A — 콘솔에 붙여넣기(가장 쉬움)", 2)
d.steps([
    [R("Firebase 콘솔 "), R("Firestore Database → 규칙(Rules)", b=True), R(" 탭으로 이동.")],
    [R("FeedWatch 폴더의 "), R("firestore.rules", mono=True), R(" 파일을 메모장으로 열어 "), R("전체 복사")],
    [R("콘솔 규칙 편집창에 "), R("전부 붙여넣기", b=True), R(" → ‘게시(Publish)’.")],
])
d.h("방법 B — 명령어로 배포(고급)", 2)
d.code([
    "npm install -g firebase-tools",
    "firebase login",
    "cd \"D:\\Users\\vmfort\\Desktop\\개발\\FeedWatch\"",
    "firebase use --add        # 프로젝트 선택",
    "firebase deploy --only firestore:rules",
])

d.pagebreak()
d.h("9. STEP 7 — 첫 관리자 만들기 (가장 중요)", 1)
d.callout("규칙은 '관리자인지'를 로그인 계정의 UID로 확인합니다. 그런데 처음에는 승인해 줄 관리자가 없으므로, 첫 관리자만 한 번 직접 만들어 줍니다. UID는 아래 명령이 대신 찾아 주므로 옮겨 적을 필요가 없습니다.", "warn")
d.steps([
    [R("데모실행(또는 배포 주소)으로 앱을 열고 "), R("본인 구글(또는 이메일/비번)로 로그인", b=True), R(" → ‘승인 대기 중’ 화면이 나옵니다. 이 화면이 떠도 계정은 만들어진 상태입니다.")],
    [R("Firebase 콘솔 "), R("프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성", b=True), R(" 으로 받은 JSON 파일을 FeedWatch 폴더에 "), R("service_account.json", mono=True), R(" 이름으로 저장합니다.")],
    [R("FeedWatch 폴더에서 명령창을 열고 아래를 실행합니다.")],
])
d.code([
    "py -m scripts.make_admin --list",
    "# Auth에 등록된 계정 목록이 나옵니다. 본인 이메일을 확인한 뒤:",
    "py -m scripts.make_admin --email 내이메일@gmail.com",
])
d.steps([
    [R("‘관리자 등록 완료’가 나오면 앱 화면을 "), R("새로고침", b=True), R(" → 관리자로 입장됩니다. 사이드바에 ‘사용자 관리·가입 신청·설정’이 보이면 성공입니다.")],
])
d.shot("make_admin 실행 결과 / 관리자로 입장한 사이드바")
d.callout("기본 구분값(공통·아빠·엄마)도 이때 함께 만들어집니다. 명령이 '계정이 없습니다'라고 하면 1번(로그인)을 아직 안 한 것입니다.", "note")

d.h("10. STEP 8 — 어디서나 접속: GitHub Pages 배포", 1)
d.p("화면은 GitHub Pages에 올리고, 데이터와 로그인은 Firebase를 그대로 씁니다. 크롤러 때문에 어차피 GitHub 저장소가 필요하므로 한 저장소로 끝납니다(Firebase Hosting은 별도 프로그램 설치가 필요해 쓰지 않습니다).")
d.steps([
    [R("GitHub에 "), R("공개(Public) 저장소", b=True), R(" 를 만들고 FeedWatch 폴더를 올립니다. 비밀 파일(.env·service_account.json)은 자동으로 빠집니다.")],
    [R("저장소 "), R("Settings → Pages → Source", b=True), R(" 를 "), R("GitHub Actions", b=True), R(" 로 지정합니다.")],
    [R("저장소 "), R("Actions", b=True), R(" 탭 → ‘Deploy web app (GitHub Pages)’ → "), R("Run workflow", b=True), R(" 실행.")],
    [R("나온 주소(https://아이디.github.io/저장소이름/)를 가족과 공유합니다.")],
    [R("Firebase 콘솔 "), R("Authentication → 설정 → 승인된 도메인", b=True), R(" 에 "), R("아이디.github.io", mono=True), R(" 를 추가합니다.")],
])
d.callout("마지막 '승인된 도메인' 추가를 빠뜨리면 배포한 주소에서 구글 로그인이 막힙니다. 꼭 하세요.", "warn")

d.pagebreak()
d.h("11. STEP 9 — 크롤러 자동화 (GitHub)", 1)
d.p("새 글을 하루 2번 자동으로 모아 오게 합니다.")
d.steps([
    [R("GitHub(https://github.com)에 가입/로그인 → "), R("새 저장소(New repository)", b=True), R(" 생성(비공개 Private 권장).")],
    [R("FeedWatch 폴더를 그 저장소에 올립니다(업로드 또는 git push).")],
    [R("Firebase 콘솔 "), R("프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성", b=True), R(" 으로 받은 JSON을 안전히 보관합니다(크롤러가 Firestore에 쓸 때 사용).")],
    [R("GitHub 저장소 "), R("Settings → Secrets and variables → Actions", b=True), R(" 에서 아래 Secrets를 등록합니다.")],
])
d.table(
    ["Secret 이름", "값"],
    [
        ["FIREBASE_PROJECT_ID", "Firebase 프로젝트 ID"],
        ["FIREBASE_SERVICE_ACCOUNT_JSON", "위 서비스 계정 키 JSON 전체 내용"],
        ["FEEDWATCH_ADMIN_EMAIL", "기본 관리자 이메일(첫 실행 때 한 번 쓰입니다)"],
        ["YOUTUBE_API_KEY", "(선택) 유튜브는 채널 주소만으로 수집됩니다. 자동 인식이 안 될 때만 필요"],
        ["FEEDWATCH_CRED_PASSPHRASE", "(로그인 사이트·비공개 네이버 카페용) 웹에서 정한 '수집 비밀번호'와 동일하게"],
        ["SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD / SMTP_FROM", "이메일(SMTP) 발송 정보"],
    ],
    [3600, 5426],
)
d.steps([
    [R("저장소 "), R("Actions", b=True), R(" 탭 → ‘FeedWatch Crawl’ 워크플로 → "), R("Run workflow", b=True), R(" 로 첫 실행을 눌러 확인합니다. 이후 매일 오전 6시·오후 6시(KST) 자동 실행됩니다.")],
])
d.callout("로그인이 필요한 사이트의 아이디/비밀번호와 비공개 네이버 카페의 로그인 쿠키는 웹 관리자(URL 관리)에서 직접 입력합니다. 최초 1회 '수집 비밀번호'를 정하면 브라우저가 그 값으로 암호화해 저장하고, 크롤러는 같은 값(위 FEEDWATCH_CRED_PASSPHRASE)으로 복호화합니다. 평문은 어디에도 저장되지 않습니다.", "note")
d.callout("메일이 실제로 나가려면 앱의 관리 → 설정 → ‘이메일 발송 방식’이 ‘자동(크롤러 환경설정 사용)’ 이어야 합니다. ‘미리보기’로 두면 파일만 만들고 발송하지 않습니다. SMTP가 일시적으로 실패하면 발송 작업을 남겨 다음 크롤링 때 자동으로 다시 시도합니다.", "note")
d.callout("인트라넷(외부에서 막힌) 사이트는 GitHub 서버가 못 들어갑니다. 그런 사이트만 내부망 PC에서 python -m crawler.main_crawler 로 직접/예약 실행하세요.", "warn")

d.h("12. STEP 10 — 가족 초대", 1)
d.steps([
    [R("가족에게 앱 주소를 알려 주고 "), R("구글 또는 이메일로 로그인", b=True), R(" 하라고 합니다.")],
    [R("처음 로그인하면 "), R("‘가입 신청’", b=True), R(" 이 자동 접수되고 ‘승인 대기’ 화면이 보입니다.")],
    [R("관리자가 앱 사이드바 "), R("관리 → 가입 신청", b=True), R(" 에서 "), R("승인", b=True), R(" 을 누르면 그때부터 입장됩니다.")],
    [R("각자 "), R("프로필 → 내 설정", b=True), R(" 에서 표시 이름과 ‘알림 받을 사이트’를 고릅니다.")],
])

d.pagebreak()
d.h("13. 비용 — 무료 한도", 1)
d.p("가족 4명, 하루 2회 수집 기준으로 모두 무료 범위입니다.")
d.table(
    ["서비스", "무료 한도", "예상 사용"],
    [
        ["GitHub Actions", "월 2,000분", "월 약 180분"],
        ["Firestore 읽기", "하루 5만 건", "하루 수백 건"],
        ["Firestore 쓰기", "하루 2만 건", "하루 수십~백 건"],
        ["Firebase 인증", "월 1만 회", "월 수십 회"],
        ["YouTube API", "하루 1만 유닛", "하루 수십 유닛"],
    ],
    [3000, 3000, 3026],
)

d.h("14. 자주 막히는 곳", 1)
d.bullet([R("로그인이 안 돼요 → ", b=True), R("승인됐는지 확인하세요. 관리자가 ‘가입 신청’에서 승인해야 입장됩니다. 첫 관리자는 7장(make_admin 명령)을 먼저 해야 합니다.")])
d.bullet([R("화면이 비어 있어요 → ", b=True), R("보안 규칙을 게시했는지(8장), 로그인 상태인지 확인하세요.")])
d.bullet([R("관리자인데 ‘사용자 관리’가 안 보여요 → ", b=True), R("7장의 make_admin 명령을 실행했는지 확인하세요. 여러 계정으로 로그인했다면 --list로 어떤 이메일이 등록됐는지 보세요.")])
d.bullet([R("새 글이 안 들어와요 → ", b=True), R("Actions에서 워크플로를 한 번 실행하고, 앱 ‘관리 → 크롤링 로그’의 실패 메시지를 확인하세요.")])
d.bullet([R("index.html을 더블클릭했더니 안 떠요 → ", b=True), R("FeedWatch_데모실행.bat 또는 호스팅 주소로 여세요(보안정책상 더블클릭은 안 됩니다).")])

d.h("15. 최종 체크리스트", 1)
for t in [
    "Firebase 프로젝트 + Firestore(서울) 생성",
    "Authentication: 이메일/비밀번호 + Google 사용 설정",
    "web/firebase_config.json 작성",
    "보안 규칙 게시(콘솔 규칙 탭에 붙여넣기)",
    "첫 관리자 등록(py -m scripts.make_admin --email …) → 관리자 입장 확인",
    "(선택) Hosting 배포 → 가족과 주소 공유",
    "GitHub 저장소 + Actions Secrets 등록 + 첫 수집 실행",
    "가족 가입 신청 → 승인 → 알림 사이트 선택",
]:
    d.bullet([R("☐  "), R(t)])

# ---------------- 파트 XML ----------------
SECT = ('<w:sectPr><w:footerReference w:type="default" r:id="rIdF"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')

document_xml = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:document {W} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    f'<w:body>{"".join(d.body)}{SECT}</w:body></w:document>'
)

def font_rpr():
    return ('<w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="Malgun Gothic" w:cs="Malgun Gothic"/>')

styles_xml = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles {W}>'
    f'<w:docDefaults><w:rPrDefault><w:rPr>{font_rpr()}<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    f'<w:style w:type="paragraph" w:styleId="DocTitle"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="0" w:after="60"/></w:pPr><w:rPr><w:b/><w:color w:val="2B2F77"/><w:sz w:val="44"/><w:szCs w:val="44"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="DocSub"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="40"/></w:pPr><w:rPr><w:color w:val="6B7280"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="6366F1"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2B2F77"/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ListB"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="80"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ListN"><w:name w:val="List Number"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="80"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Cell"><w:name w:val="Cell"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="252" w:lineRule="auto"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Callout"><w:name w:val="Callout"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="EAF1FB"/><w:spacing w:before="80" w:after="120"/><w:ind w:left="160" w:right="160"/><w:pBdr><w:left w:val="single" w:sz="18" w:space="6" w:color="6366F1"/></w:pBdr></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="CalloutWarn"><w:name w:val="CalloutWarn"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="FBF0E6"/><w:spacing w:before="80" w:after="120"/><w:ind w:left="160" w:right="160"/><w:pBdr><w:left w:val="single" w:sz="18" w:space="6" w:color="E08A2C"/></w:pBdr></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F3F4F6"/><w:spacing w:before="60" w:after="120" w:line="276" w:lineRule="auto"/><w:ind w:left="120" w:right="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Shot"><w:name w:val="Shot"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120"/></w:pPr></w:style>'
    '<w:style w:type="character" w:styleId="Mono"><w:name w:val="Mono"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:color w:val="B83280"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr></w:style>'
    '</w:styles>'
)

# numbering: abstract 0 = bullet, abstract 1 = decimal
def lvl_bullet():
    return ('<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
            '<w:pPr><w:ind w:left="460" w:hanging="280"/></w:pPr>'
            '<w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:hint="default"/></w:rPr></w:lvl>')
def lvl_decimal():
    return ('<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/>'
            '<w:pPr><w:ind w:left="460" w:hanging="320"/></w:pPr></w:lvl>')

nums_xml = "".join(f'<w:num w:numId="{nid}"><w:abstractNumId w:val="1"/></w:num>' for nid in d.nums)
numbering_xml = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:numbering {W}>'
    f'<w:abstractNum w:abstractNumId="0">{lvl_bullet()}</w:abstractNum>'
    f'<w:abstractNum w:abstractNumId="1">{lvl_decimal()}</w:abstractNum>'
    f'<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>{nums_xml}'
    '</w:numbering>'
)

footer_xml = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:ftr {W}>'
    '<w:p><w:pPr><w:jc w:val="center"/><w:rPr><w:color w:val="9AA0AC"/><w:sz w:val="17"/></w:rPr></w:pPr>'
    '<w:r><w:rPr><w:color w:val="9AA0AC"/><w:sz w:val="17"/></w:rPr><w:t xml:space="preserve">FeedWatch 클라우드 설치 설명서 · </w:t></w:r>'
    '<w:r><w:rPr><w:color w:val="9AA0AC"/><w:sz w:val="17"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:rPr><w:color w:val="9AA0AC"/><w:sz w:val="17"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    '<w:r><w:rPr><w:color w:val="9AA0AC"/><w:sz w:val="17"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
    '</w:p></w:ftr>'
)

content_types = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '</Types>'
)
root_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>'
)
doc_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
    '<Relationship Id="rIdF" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
    '</Relationships>'
)

parts = {
    "[Content_Types].xml": content_types,
    "_rels/.rels": root_rels,
    "word/document.xml": document_xml,
    "word/styles.xml": styles_xml,
    "word/numbering.xml": numbering_xml,
    "word/footer1.xml": footer_xml,
    "word/_rels/document.xml.rels": doc_rels,
}

# well-formed 검증
for name, content in parts.items():
    if name.endswith(".xml") or name.endswith(".rels"):
        minidom.parseString(content.encode("utf-8"))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, content in parts.items():
        z.writestr(name, content)

print(f"OK: {OUT} ({OUT.stat().st_size} bytes, body parts={len(d.body)}, numbered lists={len(d.nums)})")
