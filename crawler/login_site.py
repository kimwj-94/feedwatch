from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from shared.config import Settings
from shared.crypto import PassphraseCipher
from shared.models import Item, Source, item_hash, new_id
from shared.repository import BaseRepository


def crawl_login_required_source(source: Source, repository: BaseRepository, settings: Settings) -> list[Item]:
    if not source.credential_id:
        raise RuntimeError("로그인 필요 사이트에는 암호화된 로그인 정보가 필요합니다.")
    credential = repository.get_credential(source.credential_id)
    if not credential:
        raise RuntimeError(f"Credential not found: {source.credential_id}")

    # 웹에서 '수집 비밀번호'로 암호화해 저장한 값을 같은 비밀번호로 복호화
    cipher = PassphraseCipher(settings.cred_passphrase)
    username = cipher.decrypt(credential.username_encrypted)
    password = cipher.decrypt(credential.password_encrypted)

    username_selector = source.metadata.get("username_selector")
    password_selector = source.metadata.get("password_selector")
    submit_selector = source.metadata.get("submit_selector")
    post_login_wait_selector = source.metadata.get("post_login_wait_selector")
    item_selector = source.selector
    if not all([username_selector, password_selector, submit_selector, item_selector]):
        raise RuntimeError("login_required source needs username/password/submit selectors and item selector.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings.playwright_headless)
        page = browser.new_page()
        try:
            page.goto(source.url, wait_until="domcontentloaded", timeout=30000)
            page.fill(username_selector, username)
            page.fill(password_selector, password)
            page.click(submit_selector)
            if post_login_wait_selector:
                page.wait_for_selector(post_login_wait_selector, timeout=20000)
            else:
                page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_selector(item_selector, timeout=20000)
            elements = page.locator(item_selector).all()[:30]
            items: list[Item] = []
            for element in elements:
                title = " ".join((element.inner_text() or "").split())
                href = element.get_attribute("href") or ""
                if not title:
                    continue
                url = page.url if not href else page.evaluate("(href) => new URL(href, document.baseURI).href", href)
                items.append(
                    Item(
                        id=new_id("item"),
                        source_id=source.id,
                        source_name=source.name,
                        group_ids=list(source.group_ids),
                        title=title,
                        url=url,
                        hash=item_hash(source.id, title, url),
                    )
                )
            return items
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Login crawler timeout: {exc}") from exc
        finally:
            browser.close()
