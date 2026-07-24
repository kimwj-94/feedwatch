from __future__ import annotations

from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from crawler.general import crawl_general_source, entry_published
from shared.config import Settings
from shared.crypto import PassphraseCipher
from shared.models import Item, Source, item_hash, new_id
from shared.repository import BaseRepository


def crawl_naver_source(
    source: Source,
    repository: BaseRepository,
    settings: Settings,
) -> list[Item]:
    max_items = int(source.metadata.get("max_items", 30))
    for rss_url in _rss_candidates(source):
        items = _crawl_rss(source, rss_url, max_items)
        if items:
            return items

    session = _build_session(source, repository, settings)
    html, final_url = _get_html(session, source.url)
    iframe_url = _extract_iframe_url(html, final_url, source.metadata.get("iframe_selector", "iframe#cafe_main"))
    if iframe_url:
        html, final_url = _get_html(session, iframe_url)

    return _parse_html_items(source, html, final_url, max_items)


def _rss_candidates(source: Source) -> list[str]:
    candidates: list[str] = []
    explicit = source.metadata.get("rss_url")
    if explicit:
        candidates.append(explicit)
    url_lower = source.url.lower()
    if url_lower.endswith((".xml", ".rss")) or "rss" in url_lower:
        candidates.append(source.url)

    parsed = urlparse(source.url)
    if "blog.naver.com" in parsed.netloc:
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            candidates.append(f"https://rss.blog.naver.com/{parts[0]}.xml")

    deduped: list[str] = []
    for url in candidates:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def _crawl_rss(source: Source, rss_url: str, max_items: int) -> list[Item]:
    headers = _headers(source)
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return []

    feed = feedparser.parse(response.content)
    items: list[Item] = []
    for entry in feed.entries[:max_items]:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()
        if not title or not url:
            continue
        items.append(_make_item(source, title, url, entry.get("id"), entry_published(entry)))
    return items


def _build_session(
    source: Source,
    repository: BaseRepository,
    settings: Settings,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(_headers(source))
    cookie_header = None
    if source.credential_id:
        credential = repository.get_credential(source.credential_id)
        if not credential:
            raise RuntimeError(f"Credential not found: {source.credential_id}")
        if credential.cookie_encrypted:
            cookie_header = PassphraseCipher(settings.cred_passphrase).decrypt(
                credential.cookie_encrypted
            )
    # 과거 평문 저장 데이터 호환. 웹에서 다시 저장하면 암호화 credentials로 이전된다.
    cookie_header = cookie_header or source.metadata.get("cookie") or source.metadata.get("cookie_header")
    if cookie_header:
        session.headers.update({"Cookie": cookie_header})
    cookies = source.metadata.get("cookies")
    if isinstance(cookies, dict):
        session.cookies.update(cookies)
    return session


def _headers(source: Source) -> dict[str, str]:
    headers = {
        "User-Agent": source.metadata.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": source.metadata.get("referer", "https://www.naver.com/"),
    }
    extra_headers = source.metadata.get("headers")
    if isinstance(extra_headers, dict):
        headers.update({str(key): str(value) for key, value in extra_headers.items()})
    return headers


def _get_html(session: requests.Session, url: str) -> tuple[str, str]:
    response = session.get(url, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_iframe_url(html: str, base_url: str, selector: str) -> str | None:
    if not selector:
        return None
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.select_one(selector)
    if not iframe:
        return None
    src = iframe.get("src")
    if not src:
        return None
    return urljoin(base_url, src)


def _parse_html_items(source: Source, html: str, base_url: str, max_items: int) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    selector = source.selector or source.metadata.get("item_selector")
    if not selector:
        # 선택자가 없으면 페이지의 모든 링크가 글로 들어와 피드가 오염된다(general.py와 동일 정책).
        raise RuntimeError(
            "RSS를 찾지 못했습니다. 고급 설정에 rss_url 또는 게시글 선택자(item_selector)를 입력하세요."
        )
    title_selector = source.metadata.get("title_selector")
    link_selector = source.metadata.get("link_selector")
    nodes = soup.select(selector)
    items: list[Item] = []
    for node in nodes[: max_items * 2]:
        title_node = node.select_one(title_selector) if title_selector else node
        link_node = node.select_one(link_selector) if link_selector else node
        title = " ".join(title_node.get_text(" ", strip=True).split()) if title_node else ""
        href = link_node.get("href") if link_node and hasattr(link_node, "get") else ""
        if not title or not href:
            continue
        items.append(_make_item(source, title, urljoin(base_url, href)))
        if len(items) >= max_items:
            break
    if not items and source.selector:
        return crawl_general_source(source)
    return items


def _make_item(source: Source, title: str, url: str, guid: str | None = None, published_at: str | None = None) -> Item:
    return Item(
        id=new_id("item"),
        source_id=source.id,
        source_name=source.name,
        group_ids=list(source.group_ids),
        title=title,
        url=url,
        hash=item_hash(source.id, title, url, guid),
        published_at=published_at,
    )
