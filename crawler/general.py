from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from shared.models import Item, Source, item_hash, new_id

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
FEED_HINTS = ("rss", "atom", "feed+json", "feed+xml")


def entry_published(entry) -> str | None:
    """피드가 알려준 글 작성 시각(UTC ISO). 없으면 None."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=UTC).isoformat(timespec="seconds")
            except (TypeError, ValueError):
                continue
    return None


def _make_item(source: Source, title: str, url: str, guid: str | None = None, published_at: str | None = None) -> Item:
    return Item(
        id=new_id("item"), source_id=source.id, source_name=source.name,
        group_ids=list(source.group_ids), title=title, url=url,
        hash=item_hash(source.id, title, url, guid), published_at=published_at,
    )


def _parse_feed(source: Source, content: bytes, max_items: int = 30) -> list[Item]:
    feed = feedparser.parse(content)
    items: list[Item] = []
    for entry in feed.entries[:max_items]:
        title = " ".join((entry.get("title") or "").split())
        link = (entry.get("link") or "").strip()
        if title and link:
            items.append(_make_item(source, title, link, entry.get("id"), entry_published(entry)))
    return items


def discover_feed(html: str, base_url: str) -> str | None:
    """페이지의 <link rel="alternate" type="...rss/atom..."> 에서 피드 URL을 찾는다."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        typ = (link.get("type") or "").lower()
        href = link.get("href")
        if href and "alternate" in rel and any(h in typ for h in FEED_HINTS):
            return urljoin(base_url, href)
    return None


def crawl_general_source(source: Source, timeout: int = 20) -> list[Item]:
    """선택자 없이도 동작: ① URL이 피드면 바로 ② 페이지에서 RSS 자동탐지 ③ 둘 다 없으면 선택자 스크래핑."""
    response = requests.get(source.url, headers=UA, timeout=timeout)
    response.raise_for_status()
    selector = source.selector.strip()
    ctype = (response.headers.get("Content-Type") or "").lower()

    # ① URL 자체가 RSS/Atom 피드
    if any(t in ctype for t in ("xml", "rss", "atom", "json")) or re.search(r"\.(xml|rss|atom)(\?|$)", source.url, re.I):
        items = _parse_feed(source, response.content)
        if items:
            return items

    text = response.text
    # ② 선택자가 없으면 페이지에서 피드 자동탐지
    if not selector:
        feed_url = discover_feed(text, response.url)
        if feed_url:
            try:
                feed_resp = requests.get(feed_url, headers=UA, timeout=timeout)
                feed_resp.raise_for_status()
                items = _parse_feed(source, feed_resp.content)
                if items:
                    return items
            except requests.RequestException:
                pass

    # ③ 선택자 스크래핑(폴백). 선택자가 없으면 페이지의 모든 링크(메뉴·푸터)가 글로 들어와
    #    피드가 오염되므로, 수집하지 않고 실패로 알린다(관리자에게 연속실패 메일 → 선택자 입력 유도).
    if not selector:
        raise RuntimeError(
            "RSS 피드를 찾지 못했습니다. 이 사이트는 고급 설정에서 게시글 링크 선택자(예: .board-list .title a)를 입력해야 합니다."
        )
    soup = BeautifulSoup(text, "html.parser")
    nodes = soup.select(selector)
    if not nodes:
        raise RuntimeError(f"선택자에 맞는 글이 없습니다: {selector}")
    items: list[Item] = []
    for node in nodes[:30]:
        title = " ".join(node.get_text(" ", strip=True).split())
        href = node.get("href") if hasattr(node, "get") else ""
        if not title or not href:
            continue
        items.append(_make_item(source, title, urljoin(response.url, href)))
    return items
