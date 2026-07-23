from __future__ import annotations

import webbrowser
from datetime import datetime

import customtkinter as ctk

from app.ui.admin import AdminWindow
from shared.models import Group, Item, User
from shared.repository import BaseRepository


class FeedWatchApp(ctk.CTk):
    def __init__(self, repository: BaseRepository, current_user: User):
        super().__init__()
        self.repository = repository
        self.current_user = current_user
        self.title("FeedWatch")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.groups: list[Group] = []
        self.selected_group_id: str | None = None
        self.selected_archive_filter = "전체"
        self.last_refreshed = ""

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_group_panel()
        self._build_tabs()
        self._build_statusbar()
        self.refresh()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="FeedWatch", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, padx=18, pady=14, sticky="w")

        self.account_label = ctk.CTkLabel(header, text=f"{self.current_user.name} ({self.current_user.role})", text_color="#5f6368")
        self.account_label.grid(row=0, column=1, padx=(8, 12), sticky="e")

        self.refresh_label = ctk.CTkLabel(header, text="마지막 갱신: -", text_color="#5f6368")
        self.refresh_label.grid(row=0, column=2, padx=(8, 12), sticky="e")

        refresh_button = ctk.CTkButton(header, text="새로고침", width=92, command=self.refresh)
        refresh_button.grid(row=0, column=3, padx=(0, 8), pady=12)

        if self.current_user.role == "admin":
            admin_button = ctk.CTkButton(header, text="관리자", width=82, command=self.open_admin)
            admin_button.grid(row=0, column=4, padx=(0, 18), pady=12)

    def _build_group_panel(self) -> None:
        self.group_panel = ctk.CTkFrame(self, corner_radius=0)
        self.group_panel.grid(row=1, column=0, sticky="nsw")
        self.group_panel.grid_columnconfigure(0, weight=1)
        label = ctk.CTkLabel(self.group_panel, text="구분값", font=ctk.CTkFont(size=15, weight="bold"))
        label.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

    def _build_tabs(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=1, sticky="nsew", padx=16, pady=16)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(content, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        search = ctk.CTkEntry(toolbar, textvariable=self.search_var, placeholder_text="제목 검색")
        search.grid(row=0, column=0, sticky="ew")
        search.bind("<Return>", lambda _event: self.refresh())

        self.sort_var = ctk.StringVar(value="최신순")
        sort_menu = ctk.CTkOptionMenu(toolbar, variable=self.sort_var, values=["최신순", "오래된순", "사이트별"], command=lambda _v: self.refresh())
        sort_menu.grid(row=0, column=1, padx=(10, 0))

        self.tabview = ctk.CTkTabview(content)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        self.tabview.add("신규")
        self.tabview.add("보관함")
        self.tabview.add("휴지통")
        self.tabview.configure(command=self.refresh)

        self.archive_filter = ctk.CTkSegmentedButton(
            self.tabview.tab("보관함"),
            values=["전체", "읽음만", "미처리만"],
            command=self._set_archive_filter,
        )
        self.archive_filter.set("전체")
        self.archive_filter.pack(fill="x", padx=12, pady=(12, 0))

        self.list_frames: dict[str, ctk.CTkScrollableFrame] = {}
        for tab in ["신규", "보관함", "휴지통"]:
            frame = ctk.CTkScrollableFrame(self.tabview.tab(tab), fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=12, pady=12)
            self.list_frames[tab] = frame

    def _build_statusbar(self) -> None:
        self.status_label = ctk.CTkLabel(self, text="신규 0건 / 미처리 0건", anchor="w")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))

    def _set_archive_filter(self, value: str) -> None:
        self.selected_archive_filter = value
        self.refresh()

    def open_admin(self) -> None:
        if self.current_user.role != "admin":
            return
        AdminWindow(self, self.repository, on_change=self.refresh)

    def refresh(self) -> None:
        self.groups = self.repository.list_groups()
        self._render_group_buttons()
        self.last_refreshed = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.refresh_label.configure(text=f"마지막 갱신: {self.last_refreshed}")
        self._render_items()
        new_count = len(self.repository.list_items(status="new"))
        pending_count = len(self.repository.list_items(status="archived_unread"))
        self.status_label.configure(text=f"총 신규 항목 {new_count}건 / 미처리 보관 {pending_count}건")

    def _render_group_buttons(self) -> None:
        for child in self.group_panel.winfo_children()[1:]:
            child.destroy()

        all_count = len(self.repository.list_items(status="new"))
        all_button = ctk.CTkButton(
            self.group_panel,
            text=f"전체 ({all_count})",
            fg_color="#1f6aa5" if self.selected_group_id is None else "transparent",
            text_color="white" if self.selected_group_id is None else "#1f6aa5",
            command=lambda: self._select_group(None),
        )
        all_button.grid(row=1, column=0, padx=12, pady=4, sticky="ew")

        for index, group in enumerate(self.groups, start=2):
            count = len(self.repository.list_items(status="new", group_id=group.id))
            button = ctk.CTkButton(
                self.group_panel,
                text=f"{group.name} ({count})",
                fg_color="#1f6aa5" if self.selected_group_id == group.id else "transparent",
                text_color="white" if self.selected_group_id == group.id else "#1f6aa5",
                command=lambda group_id=group.id: self._select_group(group_id),
            )
            button.grid(row=index, column=0, padx=12, pady=4, sticky="ew")

    def _select_group(self, group_id: str | None) -> None:
        self.selected_group_id = group_id
        self.refresh()

    def _render_items(self) -> None:
        for frame in self.list_frames.values():
            for child in frame.winfo_children():
                child.destroy()

        self._render_tab("신규", self.repository.list_items(status="new", group_id=self.selected_group_id))

        archived = self.repository.list_items(status="read", group_id=self.selected_group_id)
        archived += self.repository.list_items(status="archived_unread", group_id=self.selected_group_id)
        if self.selected_archive_filter == "읽음만":
            archived = [item for item in archived if item.status == "read"]
        if self.selected_archive_filter == "미처리만":
            archived = [item for item in archived if item.status == "archived_unread"]
        self._render_tab("보관함", archived)

        self._render_tab("휴지통", self.repository.list_items(status="deleted", group_id=self.selected_group_id))

    def _render_tab(self, tab_name: str, items: list[Item]) -> None:
        query = self.search_var.get().strip().lower()
        if query:
            items = [item for item in items if query in item.title.lower()]
        if self.sort_var.get() == "오래된순":
            items = list(reversed(items))
        if self.sort_var.get() == "사이트별":
            items = sorted(items, key=lambda item: (item.source_name, item.fetched_at), reverse=True)

        frame = self.list_frames[tab_name]
        if not items:
            ctk.CTkLabel(frame, text="표시할 항목이 없습니다.", text_color="#6b7280").pack(anchor="w", padx=8, pady=16)
            return

        for item in items:
            ItemRow(frame, item, tab_name, self.repository, on_change=self.refresh).pack(fill="x", pady=5)


class ItemRow(ctk.CTkFrame):
    def __init__(self, parent, item: Item, tab_name: str, repository: BaseRepository, on_change):
        super().__init__(parent, corner_radius=8)
        self.item = item
        self.repository = repository
        self.on_change = on_change
        self.grid_columnconfigure(1, weight=1)

        icon, color = self._status_icon(item.status)
        ctk.CTkLabel(self, text=icon, text_color=color, width=32, font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, rowspan=2, padx=(10, 4), pady=10, sticky="n"
        )
        title = ctk.CTkLabel(self, text=item.title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w", cursor="hand2")
        title.grid(row=0, column=1, sticky="ew", padx=8, pady=(10, 2))
        title.bind("<Button-1>", lambda _event: webbrowser.open(item.url))

        meta = f"{item.source_name}  ·  {item.fetched_at.replace('T', ' ')[:16]}  ·  {item.url}"
        ctk.CTkLabel(self, text=meta, text_color="#6b7280", anchor="w").grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 10))

        if tab_name == "신규":
            ctk.CTkButton(self, text="읽음", width=64, command=self._mark_read).grid(row=0, column=2, padx=(8, 4), pady=10)
            ctk.CTkButton(self, text="삭제", width=64, fg_color="#b42318", hover_color="#912018", command=self._delete).grid(
                row=0, column=3, padx=(4, 10), pady=10
            )
        elif tab_name == "보관함":
            ctk.CTkButton(self, text="삭제", width=64, fg_color="#b42318", hover_color="#912018", command=self._delete).grid(
                row=0, column=2, padx=10, pady=10
            )
        elif tab_name == "휴지통":
            ctk.CTkButton(self, text="완전삭제", width=82, fg_color="#7f1d1d", hover_color="#601313", command=self._purge).grid(
                row=0, column=2, padx=10, pady=10
            )

    def _status_icon(self, status: str) -> tuple[str, str]:
        if status == "new":
            return "●", "#2563eb"
        if status == "read":
            return "✓", "#6b7280"
        if status == "archived_unread":
            return "!", "#f97316"
        return "×", "#9ca3af"

    def _mark_read(self) -> None:
        self.repository.set_item_status(self.item.id, "read")
        self.on_change()

    def _delete(self) -> None:
        self.repository.set_item_status(self.item.id, "deleted")
        self.on_change()

    def _purge(self) -> None:
        self.repository.permanently_delete_item(self.item.id)
        self.on_change()
