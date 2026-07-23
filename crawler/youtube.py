from __future__ import annotations

import re

import feedparser
import requests

from shared.models import Item, Source, item_hash, new_id

YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _make_item(source: Source, title: str, url: str) -> Item:
    return Item(
        id=new_id("item"), source_id=source.id, source_name=source.name,
        group_ids=list(source.group_ids), title=title, url=url, hash=item_hash(source.id, title, url),
    )


def resolve_channel_id(source: Source) -> str | None:
    """채널 ID(UC…)를 메타·URL·채널 페이지에서 찾는다. API 키 불필요."""
    cid = (source.metadata or {}).get("channel_id")
    if cid:
        return cid.strip()
    url = source.url or ""
    m = re.search(r"youtube\.com/channel/(UC[0-9A-Za-z_\-]{20,})", url)
    if m:
        return m.group(1)
    # @handle, /c/, /user/ 등은 채널 페이지 HTML에서 channelId 추출
    try:
        html = requests.get(url, headers=UA, timeout=20).text
    except requests.RequestException:
        return None
    for pat in (r'"channelId":"(UC[0-9A-Za-z_\-]{20,})"',
                r'"externalId":"(UC[0-9A-Za-z_\-]{20,})"',
                r'/channel/(UC[0-9A-Za-z_\-]{20,})'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def crawl_youtube_source(source: Source, api_key: str = "") -> list[Item]:
    max_items = int((source.metadata or {}).get("max_items", 15))
    channel_id = resolve_channel_id(source)
    if channel_id:
        resp = requests.get(YT_RSS.format(channel_id), headers=UA, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        items: list[Item] = []
        for entry in feed.entries[:max_items]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if title and link:
                items.append(_make_item(source, title, link))
        return items
    if api_key:
        return _crawl_via_api(source, api_key, max_items)
    raise RuntimeError("유튜브 채널 ID를 찾지 못했습니다. 채널 URL을 확인하거나 고급 메타에 channel_id를 입력하세요.")


def _crawl_via_api(source: Source, api_key: str, max_items: int) -> list[Item]:
    """RSS로 채널 ID를 못 찾을 때만 쓰는 폴백(YouTube Data API)."""
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=api_key)
    ref = (source.metadata or {}).get("channel_id") or source.url.rstrip("/").split("/")[-1]
    channel_id = ref
    if ref.startswith("@") or not ref.startswith("UC"):
        search = youtube.search().list(part="snippet", q=ref, type="channel", maxResults=1).execute()
        hits = search.get("items", [])
        if not hits:
            return []
        channel_id = hits[0]["snippet"]["channelId"]
    response = youtube.search().list(part="snippet", channelId=channel_id, order="date", type="video", maxResults=max_items).execute()
    found: list[Item] = []
    for video in response.get("items", []):
        vid = video["id"].get("videoId")
        if not vid:
            continue
        title = video["snippet"]["title"]
        url = f"https://www.youtube.com/watch?v={vid}"
        found.append(_make_item(source, title, url))
    return found
