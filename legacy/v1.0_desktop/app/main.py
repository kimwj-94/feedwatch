from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk

from app.auth import AuthService
from app.ui.dashboard import FeedWatchApp
from app.ui.login import LoginWindow
from shared.config import load_settings
from shared.repository import get_repository


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    settings = load_settings()
    repository = get_repository(settings)
    repository.archive_old_new_items(days=7)

    login = LoginWindow(AuthService(repository, settings))
    login.mainloop()
    if not login.session:
        return

    app = FeedWatchApp(repository, login.session.user)
    app.mainloop()


if __name__ == "__main__":
    main()
