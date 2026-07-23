from __future__ import annotations

import threading

import customtkinter as ctk

from app.auth import AuthError, AuthService, AuthSession


class LoginWindow(ctk.CTk):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        self.session: AuthSession | None = None
        self.title("FeedWatch 로그인")
        self.geometry("460x520")
        self.minsize(420, 480)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        panel = ctk.CTkFrame(self, corner_radius=8)
        panel.grid(row=0, column=0, sticky="nsew", padx=28, pady=28)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="FeedWatch", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=22, pady=(24, 2)
        )
        ctk.CTkLabel(panel, text="가족 계정으로 로그인", text_color="#6b7280").grid(
            row=1, column=0, sticky="w", padx=22, pady=(0, 18)
        )

        self.mode = ctk.StringVar(value="로컬")
        mode = ctk.CTkSegmentedButton(panel, values=["로컬", "Firebase", "Google"], variable=self.mode, command=self._switch_mode)
        mode.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 16))

        self.local_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.local_frame.grid(row=3, column=0, sticky="ew", padx=22)
        self.local_frame.grid_columnconfigure(0, weight=1)
        self.local_user = ctk.StringVar()
        self.local_user_menu = ctk.CTkOptionMenu(self.local_frame, variable=self.local_user, values=[""])
        self.local_user_menu.grid(row=0, column=0, sticky="ew")

        self.firebase_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.firebase_frame.grid_columnconfigure(0, weight=1)
        self.email_entry = ctk.CTkEntry(self.firebase_frame, placeholder_text="이메일")
        self.password_entry = ctk.CTkEntry(self.firebase_frame, placeholder_text="비밀번호", show="*")
        self.email_entry.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.password_entry.grid(row=1, column=0, sticky="ew")
        self.password_entry.bind("<Return>", lambda _event: self.login())

        self.google_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.google_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.google_frame,
            text="브라우저에서 Google 계정을 승인한 뒤 FeedWatch로 돌아옵니다.",
            text_color="#6b7280",
            wraplength=360,
        ).grid(row=0, column=0, sticky="ew")

        self.message_label = ctk.CTkLabel(panel, text="", text_color="#b42318", wraplength=360)
        self.message_label.grid(row=4, column=0, sticky="ew", padx=22, pady=(16, 8))

        self.login_button = ctk.CTkButton(panel, text="로그인", command=self.login)
        self.login_button.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 12))
        ctk.CTkLabel(panel, text="Firebase 계정은 관리자 화면의 사용자 목록에 먼저 등록되어야 합니다.", text_color="#6b7280").grid(
            row=6, column=0, sticky="ew", padx=22, pady=(0, 20)
        )

        self._load_local_users()
        self._switch_mode("로컬")

    def _load_local_users(self) -> None:
        users = self.auth_service.list_local_users()
        self.email_to_label = {f"{user.name} <{user.email}>": user.email for user in users}
        labels = list(self.email_to_label) or ["등록된 사용자가 없습니다"]
        self.local_user_menu.configure(values=labels)
        self.local_user.set(labels[0])

    def _switch_mode(self, value: str) -> None:
        if value == "Firebase":
            self.local_frame.grid_remove()
            self.google_frame.grid_remove()
            self.firebase_frame.grid(row=3, column=0, sticky="ew", padx=22)
        elif value == "Google":
            self.local_frame.grid_remove()
            self.firebase_frame.grid_remove()
            self.google_frame.grid(row=3, column=0, sticky="ew", padx=22)
        else:
            self.firebase_frame.grid_remove()
            self.google_frame.grid_remove()
            self.local_frame.grid(row=3, column=0, sticky="ew", padx=22)
        self.message_label.configure(text="")

    def login(self) -> None:
        self.login_button.configure(state="disabled")
        self.message_label.configure(text="로그인 중...")

        def worker() -> None:
            try:
                if self.mode.get() == "Firebase":
                    session = self.auth_service.firebase_email_login(self.email_entry.get().strip(), self.password_entry.get())
                elif self.mode.get() == "Google":
                    session = self.auth_service.firebase_google_login()
                else:
                    selected = self.local_user.get()
                    session = self.auth_service.local_login(self.email_to_label.get(selected, selected))
                self.after(0, lambda: self._finish_login(session))
            except AuthError as exc:
                message = str(exc)
                self.after(0, lambda message=message: self._show_error(message))
            except Exception as exc:
                message = f"로그인 실패: {exc}"
                self.after(0, lambda message=message: self._show_error(message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_login(self, session: AuthSession) -> None:
        self.session = session
        self.destroy()

    def _show_error(self, message: str) -> None:
        self.login_button.configure(state="normal")
        self.message_label.configure(text=message)
