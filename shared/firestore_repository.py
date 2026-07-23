from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore

from shared.config import Settings
from shared.models import CrawlLog, Credential, Group, Item, ItemStatus, Source, User, from_dict, new_id, parse_dt, to_dict, utc_now
from shared.repository import DEFAULT_APP_CONFIG, BaseRepository, RepositoryError


class FirestoreRepository(BaseRepository):
    """Firestore adapter for the same contract used by the local JSON store."""

    def __init__(self, settings: Settings):
        if not firebase_admin._apps:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id or None})
        self.db = firestore.client()
        self.admin_email = settings.admin_email

    def _collection(self, name: str):
        return self.db.collection(name)

    def _docs(self, name: str) -> list[dict[str, Any]]:
        return [doc.to_dict() | {"id": doc.id} for doc in self._collection(name).stream()]

    def _rows(self, name: str, model: type[Any]) -> list[Any]:
        """문서 → 모델. 웹앱이 추가한 미지 필드가 있어도 크롤러가 멈추지 않도록 from_dict로 걸러 담는다."""
        return [from_dict(model, doc) for doc in self._docs(name)]

    def seed_defaults(self) -> None:
        if not list(self._collection("groups").limit(1).stream()):
            for group in [
                Group(id="group_common", name="공통", order=1),
                Group(id="group_dad", name="아빠", order=2),
                Group(id="group_mom", name="엄마", order=3),
            ]:
                self.save_group(group)
        if not list(self._collection("users").limit(1).stream()):
            self.save_user(User(id="user_admin", name="관리자", email=self.admin_email, role="admin"))

    def list_groups(self) -> list[Group]:
        self.seed_defaults()
        return sorted(self._rows("groups", Group), key=lambda x: x.order)

    def save_group(self, group: Group) -> Group:
        if not group.id:
            group.id = new_id("group")
        self._collection("groups").document(group.id).set(to_dict(group))
        return group

    def delete_group(self, group_id: str) -> None:
        if any(group_id in src.group_ids for src in self.list_sources()):
            raise RepositoryError("이 구분값에 연결된 URL이 있어 삭제할 수 없습니다.")
        self._collection("groups").document(group_id).delete()

    def list_sources(self, active_only: bool = False) -> list[Source]:
        sources = self._rows("sources", Source)
        if active_only:
            sources = [source for source in sources if source.active]
        return sorted(sources, key=lambda x: parse_dt(x.updated_at), reverse=True)

    def save_source(self, source: Source) -> Source:
        if not source.id:
            source.id = new_id("src")
            source.created_at = utc_now()
        source.updated_at = utc_now()
        self._collection("sources").document(source.id).set(to_dict(source))
        return source

    def delete_source(self, source_id: str) -> None:
        self._collection("sources").document(source_id).delete()

    def save_credential(self, credential: Credential) -> Credential:
        if not credential.id:
            credential.id = new_id("cred")
        credential.updated_at = utc_now()
        self._collection("credentials").document(credential.id).set(to_dict(credential))
        return credential

    def get_credential(self, credential_id: str) -> Credential | None:
        doc = self._collection("credentials").document(credential_id).get()
        if not doc.exists:
            return None
        return from_dict(Credential, doc.to_dict() | {"id": doc.id})

    def delete_credential(self, credential_id: str) -> None:
        self._collection("credentials").document(credential_id).delete()

    def list_items(self, status: ItemStatus | None = None, group_id: str | None = None) -> list[Item]:
        items = self._rows("items", Item)
        if status:
            items = [item for item in items if item.status == status]
        if group_id:
            items = [item for item in items if group_id in item.group_ids]
        return sorted(items, key=lambda x: parse_dt(x.fetched_at), reverse=True)

    def add_items_dedup(self, items: list[Item]) -> list[Item]:
        existing_hashes = {item.hash for item in self.list_items()}
        new_items = [item for item in items if item.hash not in existing_hashes]
        batch = self.db.batch()
        for item in new_items:
            ref = self._collection("items").document(item.id)
            batch.set(ref, to_dict(item))
        if new_items:
            batch.commit()
        return new_items

    def set_item_status(self, item_id: str, status: ItemStatus) -> None:
        update: dict[str, Any] = {"status": status}
        now = utc_now()
        if status == "read":
            update["read_at"] = now
        if status == "deleted":
            update["deleted_at"] = now
        if status == "archived_unread":
            update["auto_archived_at"] = now
        self._collection("items").document(item_id).update(update)

    def permanently_delete_item(self, item_id: str) -> None:
        self._collection("items").document(item_id).delete()

    def archive_old_new_items(self, days: int = 7) -> int:
        threshold = datetime.now(UTC) - timedelta(days=days)
        count = 0
        for item in self.list_items(status="new"):
            if parse_dt(item.fetched_at) <= threshold:
                self.set_item_status(item.id, "archived_unread")
                count += 1
        return count

    def list_users(self) -> list[User]:
        return self._rows("users", User)

    def save_user(self, user: User) -> User:
        if not user.id:
            user.id = new_id("user")
        self._collection("users").document(user.id).set(to_dict(user))
        return user

    def list_logs(self, limit: int = 50) -> list[CrawlLog]:
        logs = self._rows("crawl_logs", CrawlLog)
        return sorted(logs, key=lambda x: parse_dt(x.run_at), reverse=True)[:limit]

    def save_log(self, log: CrawlLog) -> CrawlLog:
        self._collection("crawl_logs").document(log.id).set(to_dict(log))
        return log

    def get_app_config(self) -> dict[str, Any]:
        doc = self._collection("app_config").document("global").get()
        cfg = dict(DEFAULT_APP_CONFIG)
        if doc.exists:
            cfg.update(doc.to_dict() or {})
        return cfg

    def save_app_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        cfg = self.get_app_config()
        cfg.update(patch or {})
        self._collection("app_config").document("global").set(cfg, merge=True)
        return cfg
