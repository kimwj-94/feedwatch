from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shared.config import Settings, load_settings
from shared.models import (
    CrawlLog,
    Credential,
    Group,
    Item,
    ItemStatus,
    NotificationJob,
    Source,
    User,
    from_dict,
    new_id,
    parse_dt,
    to_dict,
    utc_now,
)


# email_provider "" = 크롤러 환경설정(EMAIL_PROVIDER/.env/Secrets)을 그대로 따름.
# 여기서 특정 값을 기본으로 두면 웹 설정이 GitHub Actions의 SMTP 설정을 덮어써 메일이 조용히 안 나간다.
DEFAULT_APP_CONFIG: dict[str, Any] = {
    "auto_archive_days": 7,
    "trash_retention_days": 30,
    "email_enabled": True,
    "email_provider": "",
    "push_enabled": True,
}


def unique_new_items(items: list[Item], existing_hashes: set[str]) -> list[Item]:
    """기존 저장분과 이번 실행 안의 중복을 모두 제거한다."""
    seen = set(existing_hashes)
    unique: list[Item] = []
    for item in items:
        if item.hash in seen:
            continue
        seen.add(item.hash)
        unique.append(item)
    return unique


class RepositoryError(RuntimeError):
    pass


class BaseRepository(ABC):
    @abstractmethod
    def seed_defaults(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_groups(self) -> list[Group]:
        raise NotImplementedError

    @abstractmethod
    def save_group(self, group: Group) -> Group:
        raise NotImplementedError

    @abstractmethod
    def delete_group(self, group_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_sources(self, active_only: bool = False) -> list[Source]:
        raise NotImplementedError

    @abstractmethod
    def save_source(self, source: Source) -> Source:
        raise NotImplementedError

    @abstractmethod
    def delete_source(self, source_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_credential(self, credential: Credential) -> Credential:
        raise NotImplementedError

    @abstractmethod
    def get_credential(self, credential_id: str) -> Credential | None:
        raise NotImplementedError

    @abstractmethod
    def delete_credential(self, credential_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_items(self, status: ItemStatus | None = None, group_id: str | None = None) -> list[Item]:
        raise NotImplementedError

    @abstractmethod
    def add_items_dedup(self, items: list[Item]) -> list[Item]:
        raise NotImplementedError

    @abstractmethod
    def set_item_status(self, item_id: str, status: ItemStatus) -> None:
        raise NotImplementedError

    @abstractmethod
    def permanently_delete_item(self, item_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def archive_old_new_items(self, days: int = 7) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_users(self) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    def save_user(self, user: User) -> User:
        raise NotImplementedError

    @abstractmethod
    def update_user_push_fids(self, user_id: str, push_fids: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_logs(self, limit: int = 50) -> list[CrawlLog]:
        raise NotImplementedError

    @abstractmethod
    def save_log(self, log: CrawlLog) -> CrawlLog:
        raise NotImplementedError

    @abstractmethod
    def list_notification_jobs(self) -> list[NotificationJob]:
        raise NotImplementedError

    @abstractmethod
    def save_notification_job(self, job: NotificationJob) -> NotificationJob:
        raise NotImplementedError

    @abstractmethod
    def delete_notification_job(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_app_config(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_app_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class LocalJsonRepository(BaseRepository):
    def __init__(self, path: Path, admin_email: str):
        self.path = path
        self.admin_email = admin_email
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty_data())
        self.seed_defaults()

    def _empty_data(self) -> dict[str, Any]:
        return {
            "users": [],
            "groups": [],
            "sources": [],
            "items": [],
            "credentials": [],
            "crawl_logs": [],
            "notification_jobs": [],
            "app_config": {},
        }

    def _read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return self._empty_data()
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def seed_defaults(self) -> None:
        data = self._read()
        changed = False
        if not data["groups"]:
            data["groups"] = [
                to_dict(Group(id="group_common", name="공통", order=1)),
                to_dict(Group(id="group_dad", name="아빠", order=2)),
                to_dict(Group(id="group_mom", name="엄마", order=3)),
            ]
            changed = True
        if not data["users"]:
            data["users"] = [
                to_dict(
                    User(
                        id="user_admin",
                        name="관리자",
                        email=self.admin_email,
                        role="admin",
                    )
                )
            ]
            changed = True
        if changed:
            self._write(data)

    def list_groups(self) -> list[Group]:
        data = self._read()
        return sorted((from_dict(Group, item) for item in data["groups"]), key=lambda x: x.order)

    def save_group(self, group: Group) -> Group:
        data = self._read()
        if not group.id:
            group.id = new_id("group")
        rows = [row for row in data["groups"] if row["id"] != group.id]
        rows.append(to_dict(group))
        data["groups"] = rows
        self._write(data)
        return group

    def delete_group(self, group_id: str) -> None:
        data = self._read()
        if any(group_id in (src.get("group_ids") or ([src["group_id"]] if src.get("group_id") else [])) for src in data["sources"]):
            raise RepositoryError("이 구분값에 연결된 URL이 있어 삭제할 수 없습니다.")
        data["groups"] = [row for row in data["groups"] if row["id"] != group_id]
        self._write(data)

    def list_sources(self, active_only: bool = False) -> list[Source]:
        data = self._read()
        sources = [from_dict(Source, item) for item in data["sources"]]
        if active_only:
            sources = [source for source in sources if source.active]
        return sorted(sources, key=lambda x: parse_dt(x.updated_at), reverse=True)

    def save_source(self, source: Source) -> Source:
        data = self._read()
        if not source.id:
            source.id = new_id("src")
            source.created_at = utc_now()
        source.updated_at = utc_now()
        rows = [row for row in data["sources"] if row["id"] != source.id]
        rows.append(to_dict(source))
        data["sources"] = rows
        self._write(data)
        return source

    def delete_source(self, source_id: str) -> None:
        data = self._read()
        data["sources"] = [row for row in data["sources"] if row["id"] != source_id]
        data["credentials"] = [row for row in data["credentials"] if row["source_id"] != source_id]
        self._write(data)

    def save_credential(self, credential: Credential) -> Credential:
        data = self._read()
        if not credential.id:
            credential.id = new_id("cred")
        credential.updated_at = utc_now()
        rows = [row for row in data["credentials"] if row["id"] != credential.id]
        rows.append(to_dict(credential))
        data["credentials"] = rows
        self._write(data)
        return credential

    def get_credential(self, credential_id: str) -> Credential | None:
        data = self._read()
        for item in data["credentials"]:
            if item["id"] == credential_id:
                return from_dict(Credential, item)
        return None

    def delete_credential(self, credential_id: str) -> None:
        data = self._read()
        data["credentials"] = [row for row in data["credentials"] if row["id"] != credential_id]
        self._write(data)

    def list_items(self, status: ItemStatus | None = None, group_id: str | None = None) -> list[Item]:
        data = self._read()
        items = [from_dict(Item, item) for item in data["items"]]
        if status:
            items = [item for item in items if item.status == status]
        if group_id:
            items = [item for item in items if group_id in item.group_ids]
        return sorted(items, key=lambda x: parse_dt(x.fetched_at), reverse=True)

    def add_items_dedup(self, items: list[Item]) -> list[Item]:
        if not items:
            return []
        data = self._read()
        existing_hashes = {item["hash"] for item in data["items"]}
        new_items = unique_new_items(items, existing_hashes)
        data["items"].extend(to_dict(item) for item in new_items)
        self._write(data)
        return new_items

    def set_item_status(self, item_id: str, status: ItemStatus) -> None:
        data = self._read()
        now = utc_now()
        for item in data["items"]:
            if item["id"] == item_id:
                item["status"] = status
                if status == "read":
                    item["read_at"] = now
                if status == "deleted":
                    item["deleted_at"] = now
                if status == "archived_unread":
                    item["auto_archived_at"] = now
                break
        self._write(data)

    def permanently_delete_item(self, item_id: str) -> None:
        data = self._read()
        data["items"] = [row for row in data["items"] if row["id"] != item_id]
        self._write(data)

    def archive_old_new_items(self, days: int = 7) -> int:
        data = self._read()
        threshold = datetime.now(UTC) - timedelta(days=days)
        count = 0
        now = utc_now()
        for item in data["items"]:
            if item["status"] == "new" and parse_dt(item["fetched_at"]) <= threshold:
                item["status"] = "archived_unread"
                item["auto_archived_at"] = now
                count += 1
        if count:
            self._write(data)
        return count

    def list_users(self) -> list[User]:
        data = self._read()
        return [from_dict(User, item) for item in data["users"]]

    def save_user(self, user: User) -> User:
        data = self._read()
        if not user.id:
            user.id = new_id("user")
        rows = [row for row in data["users"] if row["id"] != user.id]
        rows.append(to_dict(user))
        data["users"] = rows
        self._write(data)
        return user

    def update_user_push_fids(self, user_id: str, push_fids: list[str]) -> None:
        data = self._read()
        for user in data["users"]:
            if user["id"] == user_id:
                user["push_fids"] = list(dict.fromkeys(push_fids))[:5]
                user["notify_push"] = bool(user["push_fids"])
                break
        self._write(data)

    def list_logs(self, limit: int = 50) -> list[CrawlLog]:
        data = self._read()
        logs = [from_dict(CrawlLog, item) for item in data["crawl_logs"]]
        return sorted(logs, key=lambda x: parse_dt(x.run_at), reverse=True)[:limit]

    def save_log(self, log: CrawlLog) -> CrawlLog:
        data = self._read()
        data["crawl_logs"].append(to_dict(log))
        self._write(data)
        return log

    def list_notification_jobs(self) -> list[NotificationJob]:
        data = self._read()
        jobs = [from_dict(NotificationJob, item) for item in data.get("notification_jobs", [])]
        return sorted(jobs, key=lambda x: parse_dt(x.created_at))

    def save_notification_job(self, job: NotificationJob) -> NotificationJob:
        data = self._read()
        rows = [row for row in data.get("notification_jobs", []) if row["id"] != job.id]
        rows.append(to_dict(job))
        data["notification_jobs"] = rows
        self._write(data)
        return job

    def delete_notification_job(self, job_id: str) -> None:
        data = self._read()
        data["notification_jobs"] = [
            row for row in data.get("notification_jobs", []) if row["id"] != job_id
        ]
        self._write(data)

    def get_app_config(self) -> dict[str, Any]:
        data = self._read()
        cfg = dict(DEFAULT_APP_CONFIG)
        cfg.update(data.get("app_config") or {})
        return cfg

    def save_app_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        cfg = dict(DEFAULT_APP_CONFIG)
        cfg.update(data.get("app_config") or {})
        cfg.update(patch or {})
        data["app_config"] = cfg
        self._write(data)
        return cfg


def get_repository(settings: Settings | None = None) -> BaseRepository:
    settings = settings or load_settings()
    if settings.storage == "local":
        return LocalJsonRepository(settings.local_store, settings.admin_email)
    if settings.storage == "firestore":
        from shared.firestore_repository import FirestoreRepository

        return FirestoreRepository(settings)
    raise RepositoryError(f"Unsupported FEEDWATCH_STORAGE value: {settings.storage}")
