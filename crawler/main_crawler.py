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
from crawler.notifier import notify_failures, notify_new_items
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
        return crawl_naver_source(source)
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

    for index, source in enumerate(sources):
        try:
            collected.extend(crawl_with_retry(source, repository, settings))
            success_count += 1
            if source.consecutive_failures or source.last_error:
                source.consecutive_failures = 0
                source.last_error = None
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
    users = repository.list_users()

    preview = None
    if config.get("email_enabled", True) and new_items:
        preview = notify_new_items(settings, users, new_items, group_names)
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
        error_messages=error_messages,
        duration_seconds=round(time.time() - started, 2),
    )
    repository.save_log(log)

    print(
        f"FeedWatch crawl complete: sources={len(sources)}, success={success_count}, "
        f"failed={len(failed_sources)}, new_items={len(new_items)}"
    )
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
