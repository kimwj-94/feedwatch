from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import customtkinter as ctk

from shared.config import load_settings
from shared.crypto import CredentialCipher, CryptoError
from shared.diagnostics import diagnostics_summary, run_diagnostics
from shared.models import Credential, Group, Source, User, new_id
from shared.repository import BaseRepository, RepositoryError


class AdminWindow(ctk.CTkToplevel):
    def __init__(self, parent, repository: BaseRepository, on_change):
        super().__init__(parent)
        self.repository = repository
        self.on_change = on_change
        self.title("FeedWatch 관리자")
        self.geometry("980x680")
        self.transient(parent)
        self.grab_set()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=16)
        for tab in ["URL 관리", "구분값 관리", "사용자 관리", "크롤링 로그", "설정"]:
            self.tabview.add(tab)

        self._build_sources_tab()
        self._build_groups_tab()
        self._build_users_tab()
        self._build_logs_tab()
        self._build_settings_tab()
        self.refresh_all()

    def _build_sources_tab(self) -> None:
        tab = self.tabview.tab("URL 관리")
        tab.grid_columnconfigure(0, weight=2)
        tab.grid_columnconfigure(1, weight=3)
        tab.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(tab)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.grid_columnconfigure(1, weight=1)

        self.source_name = ctk.CTkEntry(form, placeholder_text="사이트명")
        self.source_url = ctk.CTkEntry(form, placeholder_text="URL")
        self.source_selector = ctk.CTkEntry(form, placeholder_text="CSS Selector 또는 XPath")
        self.source_type = ctk.StringVar(value="general")
        self.source_group = ctk.StringVar()
        self.source_active = ctk.BooleanVar(value=True)

        rows = [
            ("사이트명", self.source_name),
            ("URL", self.source_url),
            ("선택자", self.source_selector),
        ]
        for row, (label, widget) in enumerate(rows):
            ctk.CTkLabel(form, text=label).grid(row=row, column=0, padx=12, pady=8, sticky="w")
            widget.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(form, text="사이트 유형").grid(row=3, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkOptionMenu(form, variable=self.source_type, values=["general", "youtube", "naver", "login_required"]).grid(
            row=3, column=1, padx=12, pady=8, sticky="ew"
        )
        ctk.CTkLabel(form, text="구분값").grid(row=4, column=0, padx=12, pady=8, sticky="w")
        self.source_group_menu = ctk.CTkOptionMenu(form, variable=self.source_group, values=["공통"])
        self.source_group_menu.grid(row=4, column=1, padx=12, pady=8, sticky="ew")
        ctk.CTkLabel(form, text="로그인 정보").grid(row=5, column=0, padx=12, pady=8, sticky="w")
        login_box = ctk.CTkFrame(form, fg_color="transparent")
        login_box.grid(row=5, column=1, padx=12, pady=8, sticky="ew")
        login_box.grid_columnconfigure((0, 1), weight=1)
        self.source_username = ctk.CTkEntry(login_box, placeholder_text="로그인 아이디")
        self.source_password = ctk.CTkEntry(login_box, placeholder_text="로그인 비밀번호", show="*")
        self.source_username.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.source_password.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        ctk.CTkLabel(form, text="고급 메타").grid(row=6, column=0, padx=12, pady=8, sticky="nw")
        metadata_tools = ctk.CTkFrame(form, fg_color="transparent")
        metadata_tools.grid(row=6, column=1, padx=12, pady=(8, 0), sticky="ew")
        metadata_tools.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(metadata_tools, text="메타 예시 적용", width=110, command=self.apply_metadata_template).grid(
            row=0, column=1, sticky="e"
        )
        self.source_metadata = ctk.CTkTextbox(form, height=92)
        self.source_metadata.grid(row=7, column=1, padx=12, pady=(4, 8), sticky="ew")
        self.source_metadata.insert(
            "1.0",
            json.dumps(self._metadata_template("general"), ensure_ascii=False, indent=2),
        )

        ctk.CTkCheckBox(form, text="활성화", variable=self.source_active).grid(row=8, column=1, padx=12, pady=8, sticky="w")
        ctk.CTkButton(form, text="URL 등록", command=self.add_source).grid(row=9, column=1, padx=12, pady=12, sticky="e")

        self.sources_frame = ctk.CTkScrollableFrame(tab)
        self.sources_frame.grid(row=0, column=1, sticky="nsew", pady=10)

    def _build_groups_tab(self) -> None:
        tab = self.tabview.tab("구분값 관리")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        bar.grid_columnconfigure(0, weight=1)
        self.group_name = ctk.CTkEntry(bar, placeholder_text="새 구분값 이름")
        self.group_name.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(bar, text="추가", width=72, command=self.add_group).grid(row=0, column=1, padx=(8, 0))
        self.groups_frame = ctk.CTkScrollableFrame(tab)
        self.groups_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _build_users_tab(self) -> None:
        tab = self.tabview.tab("사용자 관리")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        form = ctk.CTkFrame(tab, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        form.grid_columnconfigure(0, weight=1)
        self.user_email = ctk.CTkEntry(form, placeholder_text="가족 이메일")
        self.user_email.grid(row=0, column=0, sticky="ew")
        self.user_name = ctk.CTkEntry(form, placeholder_text="이름")
        self.user_name.grid(row=0, column=1, padx=8)
        self.user_role = ctk.StringVar(value="member")
        ctk.CTkOptionMenu(form, variable=self.user_role, values=["admin", "member"], width=110).grid(row=0, column=2)
        ctk.CTkButton(form, text="추가", width=72, command=self.add_user).grid(row=0, column=3, padx=(8, 0))
        self.users_frame = ctk.CTkScrollableFrame(tab)
        self.users_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _build_logs_tab(self) -> None:
        tab = self.tabview.tab("크롤링 로그")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        bar.grid_columnconfigure(0, weight=1)
        self.crawl_status_label = ctk.CTkLabel(bar, text="수동 크롤링을 실행할 수 있습니다.", anchor="w")
        self.crawl_status_label.grid(row=0, column=0, sticky="ew")
        self.crawl_button = ctk.CTkButton(bar, text="지금 크롤링 실행", width=130, command=self.run_manual_crawl)
        self.crawl_button.grid(row=0, column=1, padx=(10, 0))
        self.logs_frame = ctk.CTkScrollableFrame(tab)
        self.logs_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _build_settings_tab(self) -> None:
        tab = self.tabview.tab("설정")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        text = (
            "기본 자동 보관 기간: 7일\n"
            "이메일 알림: SMTP 설정이 있으면 발송, 없으면 data/last_email_preview.html 생성\n"
            "Firebase 전환: .env의 FEEDWATCH_STORAGE=firestore 및 GOOGLE_APPLICATION_CREDENTIALS 설정"
        )
        ctk.CTkLabel(tab, text=text, justify="left").grid(row=0, column=0, sticky="w", padx=14, pady=(16, 10))
        self.diagnostics_button = ctk.CTkButton(tab, text="환경 진단 실행", width=120, command=self.run_diagnostics)
        self.diagnostics_button.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        self.diagnostics_text = ctk.CTkTextbox(tab, height=260)
        self.diagnostics_text.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.diagnostics_text.insert("1.0", "환경 진단을 실행하면 설정 상태가 표시됩니다.")
        self.diagnostics_text.configure(state="disabled")

    def refresh_all(self) -> None:
        self._refresh_source_group_menu()
        self._render_sources()
        self._render_groups()
        self._render_users()
        self._render_logs()
        self.on_change()

    def _refresh_source_group_menu(self) -> None:
        groups = self.repository.list_groups()
        names = [group.name for group in groups] or ["공통"]
        self.group_name_to_id = {group.name: group.id for group in groups}
        self.source_group_menu.configure(values=names)
        if not self.source_group.get() or self.source_group.get() not in names:
            self.source_group.set(names[0])

    def add_source(self) -> None:
        name = self.source_name.get().strip()
        url = self.source_url.get().strip()
        if not name or not url:
            return
        try:
            metadata = json.loads(self.source_metadata.get("1.0", "end").strip() or "{}")
        except json.JSONDecodeError as exc:
            self._toast(f"고급 메타 JSON 형식이 올바르지 않습니다: {exc}")
            return
        source = Source(
            id="",
            name=name,
            url=url,
            group_id=self.group_name_to_id[self.source_group.get()],
            type=self.source_type.get(),
            selector=self.source_selector.get().strip(),
            active=self.source_active.get(),
            metadata=metadata,
        )
        source = self.repository.save_source(source)
        username = self.source_username.get().strip()
        password = self.source_password.get().strip()
        if username or password:
            try:
                cipher = CredentialCipher(load_settings().encryption_key)
            except CryptoError as exc:
                self.repository.delete_source(source.id)
                self._toast(str(exc))
                return
            credential = self.repository.save_credential(
                Credential(
                    id="",
                    source_id=source.id,
                    username_encrypted=cipher.encrypt(username),
                    password_encrypted=cipher.encrypt(password),
                )
            )
            source.credential_id = credential.id
            self.repository.save_source(source)
        for widget in [self.source_name, self.source_url, self.source_selector, self.source_username, self.source_password]:
            widget.delete(0, "end")
        self.refresh_all()

    def apply_metadata_template(self) -> None:
        self.source_metadata.delete("1.0", "end")
        self.source_metadata.insert(
            "1.0",
            json.dumps(self._metadata_template(self.source_type.get()), ensure_ascii=False, indent=2),
        )

    def _metadata_template(self, source_type: str) -> dict:
        if source_type == "naver":
            return {
                "rss_url": "",
                "iframe_selector": "iframe#cafe_main",
                "item_selector": "",
                "title_selector": "",
                "link_selector": "",
                "cookie": "",
                "max_items": 30,
            }
        if source_type == "login_required":
            return {
                "username_selector": "",
                "password_selector": "",
                "submit_selector": "",
                "post_login_wait_selector": "",
            }
        if source_type == "youtube":
            return {
                "channel_id": "",
                "max_items": 10,
            }
        return {}

    def add_group(self) -> None:
        name = self.group_name.get().strip()
        if not name:
            return
        order = len(self.repository.list_groups()) + 1
        self.repository.save_group(Group(id="", name=name, order=order))
        self.group_name.delete(0, "end")
        self.refresh_all()

    def add_user(self) -> None:
        email = self.user_email.get().strip()
        if not email:
            return
        name = self.user_name.get().strip() or email.split("@")[0]
        self.repository.save_user(User(id=new_id("user"), name=name, email=email, role=self.user_role.get()))
        self.user_email.delete(0, "end")
        self.user_name.delete(0, "end")
        self.refresh_all()

    def _render_sources(self) -> None:
        self._clear(self.sources_frame)
        groups = {group.id: group.name for group in self.repository.list_groups()}
        for source in self.repository.list_sources():
            row = ctk.CTkFrame(self.sources_frame)
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
            status = "ON" if source.active else "OFF"
            text = f"{source.name} [{source.type}/{status}]  ·  {groups.get(source.group_id, source.group_id)}\n{source.url}"
            if source.credential_id:
                text += "\n로그인 정보: 암호화 저장됨"
            ctk.CTkLabel(row, text=text, justify="left", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="ew")
            ctk.CTkButton(row, text="삭제", width=64, fg_color="#b42318", hover_color="#912018", command=lambda sid=source.id: self.delete_source(sid)).grid(
                row=0, column=1, padx=10
            )

    def _render_groups(self) -> None:
        self._clear(self.groups_frame)
        for group in self.repository.list_groups():
            row = ctk.CTkFrame(self.groups_frame)
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"{group.order}. {group.name}", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="ew")
            ctk.CTkButton(row, text="삭제", width=64, command=lambda gid=group.id: self.delete_group(gid)).grid(row=0, column=1, padx=10)

    def _render_users(self) -> None:
        self._clear(self.users_frame)
        for user in self.repository.list_users():
            row = ctk.CTkFrame(self.users_frame)
            row.pack(fill="x", pady=5)
            text = f"{user.name}  ·  {user.email}  ·  {user.role}  ·  알림 {'ON' if user.notify_email else 'OFF'}"
            ctk.CTkLabel(row, text=text, anchor="w").pack(fill="x", padx=10, pady=8)

    def _render_logs(self) -> None:
        self._clear(self.logs_frame)
        logs = self.repository.list_logs()
        if not logs:
            ctk.CTkLabel(self.logs_frame, text="아직 크롤링 로그가 없습니다.", text_color="#6b7280").pack(anchor="w", padx=8, pady=14)
            return
        for log in logs:
            row = ctk.CTkFrame(self.logs_frame)
            row.pack(fill="x", pady=5)
            text = (
                f"{log.run_at.replace('T', ' ')[:16]}  ·  신규 {log.new_items_count}건  ·  "
                f"성공 {log.success_count}/{log.total_sources}  ·  실패 {log.fail_count}  ·  {log.duration_seconds:.1f}s"
            )
            ctk.CTkLabel(row, text=text, anchor="w").pack(fill="x", padx=10, pady=8)

    def delete_source(self, source_id: str) -> None:
        self.repository.delete_source(source_id)
        self.refresh_all()

    def run_manual_crawl(self) -> None:
        self.crawl_button.configure(state="disabled")
        self.crawl_status_label.configure(text="크롤링 실행 중...")

        def worker() -> None:
            root = Path(__file__).resolve().parents[2]
            result = subprocess.run(
                [sys.executable, "-m", "crawler.main_crawler"],
                cwd=root,
                text=True,
                capture_output=True,
            )
            message = (result.stdout or result.stderr or "").strip().splitlines()
            summary = message[0] if message else f"크롤링 종료 코드: {result.returncode}"
            self.after(0, lambda: self._finish_manual_crawl(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_manual_crawl(self, summary: str) -> None:
        self.crawl_button.configure(state="normal")
        self.crawl_status_label.configure(text=summary)
        self.refresh_all()

    def run_diagnostics(self) -> None:
        self.diagnostics_button.configure(state="disabled")
        self._set_diagnostics_text("환경 진단 실행 중...")

        def worker() -> None:
            summary = diagnostics_summary(run_diagnostics())
            self.after(0, lambda: self._finish_diagnostics(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_diagnostics(self, summary: str) -> None:
        self.diagnostics_button.configure(state="normal")
        self._set_diagnostics_text(summary)

    def _set_diagnostics_text(self, text: str) -> None:
        self.diagnostics_text.configure(state="normal")
        self.diagnostics_text.delete("1.0", "end")
        self.diagnostics_text.insert("1.0", text)
        self.diagnostics_text.configure(state="disabled")

    def delete_group(self, group_id: str) -> None:
        try:
            self.repository.delete_group(group_id)
        except RepositoryError as exc:
            self._toast(str(exc))
        self.refresh_all()

    def _toast(self, message: str) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("알림")
        popup.geometry("360x120")
        ctk.CTkLabel(popup, text=message, wraplength=320).pack(expand=True, padx=16, pady=16)
        ctk.CTkButton(popup, text="확인", width=72, command=popup.destroy).pack(pady=(0, 14))

    def _clear(self, frame) -> None:
        for child in frame.winfo_children():
            child.destroy()
