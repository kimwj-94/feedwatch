from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from typing import Any, Literal


ItemStatus = Literal["new", "read", "archived_unread", "deleted"]
SourceType = Literal["general", "youtube", "naver", "login_required"]
UserRole = Literal["admin", "member"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def item_hash(source_id: str, title: str, url: str, guid: str | None = None) -> str:
    """'같은 글인가'를 판단하는 지문.

    기준 우선순위: 피드가 준 고유 ID(guid) > 글 주소 > 제목.
    제목을 지문에 넣으면 오탈자 하나만 고쳐도 새 글로 잡혀 알림이 다시 가므로 제외한다.
    주소도 ID도 없는 게시판(선택자 수집)에서만 제목을 쓴다.
    """
    key = (guid or "").strip() or url.strip() or title.strip()
    raw = f"{source_id}|{key}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class User:
    id: str
    name: str
    email: str
    role: UserRole = "member"
    notify_email: bool = True
    notify_sources: list[str] = field(default_factory=list)  # 알림 받을 사이트(빈 목록=전체)
    last_seen: str | None = None  # 본인 마지막 확인 시각('내 미확인' 계산용)
    created_at: str = field(default_factory=utc_now)
    last_login: str | None = None


@dataclass
class Group:
    id: str
    name: str
    order: int
    color_index: int | None = None  # 웹에서 고른 칩 색(0~7). 미지정이면 순서대로 자동 배정.
    created_at: str = field(default_factory=utc_now)


@dataclass
class Source:
    id: str
    name: str
    url: str
    group_ids: list[str] = field(default_factory=list)  # 한 사이트에 구분값 여러 개 지정 가능
    type: SourceType = "general"
    selector: str = ""
    active: bool = True
    credential_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0
    last_error: str | None = None
    # 첫 수집인지 여부. 사이트를 새로 등록하면 기존 글이 한꺼번에 '신규'로 잡히는데,
    # 그걸 전부 메일로 보내면 알림 폭탄이 된다. 첫 수집분은 앱에만 담고 알림은 건너뛴다.
    first_crawl_done: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class Credential:
    id: str
    source_id: str
    username_encrypted: str
    password_encrypted: str
    updated_at: str = field(default_factory=utc_now)


@dataclass
class Item:
    id: str
    source_id: str
    source_name: str
    group_ids: list[str]      # 수집 시점의 사이트 구분값들을 그대로 복사해 둔다
    title: str
    url: str
    hash: str
    status: ItemStatus = "new"
    published_at: str | None = None      # 사이트가 알려준 글 작성 시각(없을 수 있음)
    fetched_at: str = field(default_factory=utc_now)   # 우리가 발견한 시각 — 정렬·미확인 판정 기준
    read_at: str | None = None
    deleted_at: str | None = None
    auto_archived_at: str | None = None


@dataclass
class CrawlLog:
    id: str
    run_at: str
    total_sources: int
    success_count: int
    fail_count: int
    new_items_count: int
    failed_sources: list[str] = field(default_factory=list)
    error_messages: dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def from_dict(model: type[Any], value: dict[str, Any]) -> Any:
    # 모델에 없는 키(과거 스키마의 잔재 등)는 무시해 하위호환을 보장한다.
    allowed = {f.name for f in fields(model)}
    data = {k: v for k, v in value.items() if k in allowed}
    # 구분값 단일(group_id) → 복수(group_ids) 이전 데이터 호환
    if "group_ids" in allowed and not data.get("group_ids"):
        legacy = value.get("group_id")
        data["group_ids"] = [legacy] if legacy else []
    return model(**data)
