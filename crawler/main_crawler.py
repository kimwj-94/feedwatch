from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from crawler.general import crawl_general_source
from crawler.login_site import crawl_login_required_source
from crawler.naver import crawl_naver_source
from crawler.notifier import (
    deliver_pending_notifications,
    notify_failures,
    notify_new_items,
    queue_new_item_notifications,
)
from crawler.youtube import crawl_youtube_source
from shared.config import load_settings
from shared.models import CrawlLog, Item, new_id, parse_dt, utc_now
from shared.repository import get_repository

FAILURE_THRESHOLD = 3
NETWORK_ERRORS = (requests.RequestException, ConnectionError, TimeoutError)


def purge_old_trash(repository, days: int) -> int:
    """휴지통(삭제) 항목을 N일 후 영구 삭제 — Firestore 용량/무료한도 관리."""
    if days <= 0:
        return 0
    threshold = datetime.now(UTC) - timedelta(days=days)
    purged = 0
    for item in repository.list_items(status="deleted"):
        if parse_dt(item.deleted_at or item.fetched_at) <= threshold:
            repository.permanently_delete_item(item.id)
            purged += 1
    return purged


def crawl_source(source, repository, settings) -> list[Item]:
    if source.type == "general":
        return crawl_general_source(source)
    if source.type == "youtube":
        return crawl_youtube_source(source, settings.youtube_api_key)
    if source.type == "naver":
        return crawl_naver_source(source, repository, settings)
    if source.type == "login_required":
        return crawl_login_required_source(source, repository, settings)
    raise ValueError(f"Unsupported source type: {source.type}")


def crawl_with_retry(source, repository, settings, attempts: int = 3) -> list[Item]:
    """Retry only transient network errors with exponential backoff (spec 4-2)."""
    for attempt in range(1, attempts + 1):
        try:
            return crawl_source(source, repository, settings)
        except NETWORK_ERRORS:
            if attempt >= attempts:
                raise
            time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))
    return []  # unreachable


def run(source_filter: str | None = None) -> int:
    started = time.time()
    settings = load_settings()
    repository = get_repository(settings)
    config = repository.get_app_config()

    days = int(config.get("auto_archive_days", 7) or 7)
    repository.archive_old_new_items(days=days)
    purge_old_trash(repository, int(config.get("trash_retention_days", 30) or 30))

    # 이메일 발송 방식은 웹 설정(app_config)을 우선 적용해 한 곳에서 관리
    settings = replace(settings, email_provider=str(config.get("email_provider") or settings.email_provider))

    sources = repository.list_sources(active_only=True)
    if source_filter:
        sources = [s for s in sources if s.id == source_filter or s.name == source_filter]

    group_names = {group.id: group.name for group in repository.list_groups()}
    failed_sources: list[str] = []
    error_messages: dict[str, str] = {}
    collected: list[Item] = []
    success_count = 0
    newly_failing: list[tuple[str, str]] = []  # crossed the failure threshold this run
    completed_first_crawls = []

    # 이번에 처음 수집하는 사이트 — 기존 글이 한꺼번에 '신규'로 잡히므로 알림에서 제외한다.
    first_time_source_ids = {s.id for s in sources if not s.first_crawl_done}

    for index, source in enumerate(sources):
        try:
            collected.extend(crawl_with_retry(source, repository, settings))
            success_count += 1
            changed = False
            if source.consecutive_failures or source.last_error:
                source.consecutive_failures = 0
                source.last_error = None
                changed = True
            if not source.first_crawl_done:
                # 항목 저장이 성공한 뒤에만 완료로 기록한다. 먼저 표시하면 저장 실패 다음 실행에
                # 기존 글이 새 글 알림으로 나갈 수 있다.
                completed_first_crawls.append(source)
            if changed:
                repository.save_source(source)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            failed_sources.append(source.id)
            error_messages[source.id] = message
            previous = source.consecutive_failures or 0
            source.consecutive_failures = previous + 1
            source.last_error = message
            repository.save_source(source)
            if previous < FAILURE_THRESHOLD <= source.consecutive_failures:
                newly_failing.append((source.name, message))
        if index < len(sources) - 1:
            time.sleep(random.uniform(settings.crawl_min_delay, settings.crawl_max_delay))

    new_items = repository.add_items_dedup(collected)
    for source in completed_first_crawls:
        source.first_crawl_done = True
        repository.save_source(source)
    users = repository.list_users()

    # 첫 수집분은 앱에는 담기지만(위에서 이미 저장됨) 메일로는 보내지 않는다.
    notifiable = [item for item in new_items if item.source_id not in first_time_source_ids]
    silenced = len(new_items) - len(notifiable)

    preview = None
    email_notes: list[str] = []
    if silenced:
        email_notes.append(
            f"처음 수집한 사이트의 기존 글 {silenced}건은 알림에서 제외했습니다(앱에서는 보입니다). "
            "다음 수집부터 새 글만 알려 드립니다."
        )
    if not config.get("email_enabled", True):
        if notifiable:
            email_notes.append("설정에서 이메일 알림이 꺼져 있어 발송하지 않았습니다.")
    elif settings.email_provider in {"gmail", "smtp"}:
        if notifiable:
            email_notes.extend(
                queue_new_item_notifications(repository, users, notifiable, group_names)
            )
        email_notes.extend(deliver_pending_notifications(settings, repository))
    elif notifiable:
        preview, notes = notify_new_items(settings, users, notifiable, group_names)
        email_notes.extend(notes)
    if newly_failing:
        notify_failures(settings, users, newly_failing)

    log = CrawlLog(
        id=new_id("log"),
        run_at=utc_now(),
        total_sources=len(sources),
        success_count=success_count,
        fail_count=len(failed_sources),
        new_items_count=len(new_items),
        failed_sources=failed_sources,
        # 이메일 문제는 앱의 '크롤링 로그'에서도 보이게 남긴다(조용한 실패 방지).
        error_messages={**error_messages, **({"이메일": " / ".join(email_notes)} if email_notes else {})},
        duration_seconds=round(time.time() - started, 2),
    )
    repository.save_log(log)

    print(
        f"FeedWatch crawl complete: sources={len(sources)}, success={success_count}, "
        f"failed={len(failed_sources)}, new_items={len(new_items)}"
    )
    for note in email_notes:
        print(f"[EMAIL] {note}")
    if preview:
        print(f"Email preview written to {preview}")
    for source_id, message in error_messages.items():
        print(f"[FAILED] {source_id}: {message}")
    # 개별 사이트 실패는 앱의 '연속실패' 표시와 관리자 메일로 알리므로 실행 자체는 성공으로 둔다.
    # (매번 빨간 X가 뜨면 진짜 장애를 놓친다.) 전부 실패한 경우만 실패 코드로 알린다.
    return 1 if sources and success_count == 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FeedWatch 크롤러")
    parser.add_argument("--source", default=None, help="특정 소스 ID 또는 이름만 크롤링합니다.")
    args = parser.parse_args()
    return run(args.source)


if __name__ == "__main__":
    raise SystemExit(main())
