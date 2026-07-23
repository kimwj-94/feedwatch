"""개발용 정적 서버 — 캐시 비활성(no-store). 코드 수정이 미리보기에 즉시 반영되게 한다.
일반 실행/배포에는 불필요(데모는 FeedWatch_데모실행.bat 사용). 미리보기/개발 검증용.
사용: py scripts/devserver.py [port] [directory]
"""
from __future__ import annotations

import http.server
import os
import sys
from functools import partial
from http.server import ThreadingHTTPServer


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def send_head(self):
        # 조건부 요청(304) 방지 — 항상 최신본(200)을 보낸다
        for h in ("If-Modified-Since", "If-None-Match"):
            if h in self.headers:
                del self.headers[h]
        return super().send_head()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5181
    directory = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    handler = partial(NoCacheHandler, directory=directory)
    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"no-cache dev server: http://localhost:{port}  (dir={directory})")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
