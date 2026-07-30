from __future__ import annotations

import os
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        pass

    def do_GET(self) -> None:
        # 실제 운영 폴더에 비공개 firebase_config.json이 있어도 이 검사는
        # 항상 데모 모드의 화면·동작만 재현해야 한다.
        if self.path.split("?", 1)[0] == "/firebase_config.json":
            self.send_error(404)
            return
        super().do_GET()


@unittest.skipUnless(
    os.getenv("FEEDWATCH_RUN_WEB_SMOKE") == "1",
    "브라우저 설치가 필요한 별도 CI 작업에서 실행합니다.",
)
class WebDemoSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        handler = partial(QuietHandler, directory=str(WEB))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_demo_login_dashboard_profile_and_mobile_layout(self) -> None:
        context = self.browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        page.goto(self.base_url, wait_until="networkidle")
        page.locator("#demo-user").select_option("user_admin")
        page.get_by_role("button", name="로그인", exact=True).click()
        page.get_by_role("heading", name="대시보드").wait_for()
        self.assertTrue(page.get_by_text("내 알림", exact=False).first.is_visible())

        page.get_by_role("button", name="메뉴").click()
        page.locator(".profile__btn").click()
        page.get_by_text("내 설정", exact=True).click()
        self.assertTrue(page.get_by_text("이 기기에서 모바일·PC 팝업 알림 받기").is_visible())
        self.assertTrue(page.get_by_text("데모 모드에서는 실제 푸시 알림을 등록하지 않습니다.").is_visible())

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        self.assertLessEqual(overflow, 1)
        self.assertEqual(errors, [])
        context.close()
