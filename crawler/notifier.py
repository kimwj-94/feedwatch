from __future__ import annotations

import base64
import html
import smtplib
from collections import OrderedDict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from shared.config import ROOT_DIR, Settings
from shared.models import Item, User


def _esc(value: str) -> str:
    return html.escape(value or "")


def build_email_html(items: list[Item], group_names: dict[str, str] | None = None) -> str:
    """New-items email, grouped by 사이트(source) — matches the per-site subscription model."""
    group_names = group_names or {}
    grouped: "OrderedDict[str, list[Item]]" = OrderedDict()
    for item in items:
        grouped.setdefault(item.source_name, []).append(item)

    sections = []
    for source_name, source_items in grouped.items():
        labels = [group_names.get(gid, "") for gid in (source_items[0].group_ids or [])]
        group_label = " · ".join(label for label in labels if label)
        tag = f" <span style=\"color:#9325a8;font-size:12px\">[{_esc(group_label)}]</span>" if group_label else ""
        rows = "".join(
            "<li style=\"margin:8px 0\">"
            f"<a href=\"{_esc(item.url)}\" style=\"color:#6c63ff;text-decoration:none;font-weight:600\">{_esc(item.title)}</a>"
            "</li>"
            for item in source_items
        )
        sections.append(
            f"<h3 style=\"margin:18px 0 6px;font-size:15px\">📌 {_esc(source_name)} "
            f"<span style=\"color:#9a968d;font-weight:500\">— {len(source_items)}건</span>{tag}</h3>"
            f"<ul style=\"margin:0;padding-left:18px;list-style:none\">{rows}</ul>"
        )

    return (
        "<html><body style=\"font-family:'Pretendard','Malgun Gothic',sans-serif;color:#232220;max-width:640px;margin:0 auto\">"
        "<h2 style=\"color:#6c63ff\">FeedWatch에 새 글이 올라왔어요</h2>"
        f"<p style=\"color:#6b6862\">알림 신청한 사이트에 새 글 {len(items)}건이 추가되었습니다.</p>"
        f"{''.join(sections)}"
        "<p style=\"margin-top:24px;color:#6b6862;font-size:13px\">FeedWatch 대시보드에서 전체 내역을 확인하세요.</p>"
        "</body></html>"
    )


def build_failure_html(failures: list[tuple[str, str]]) -> str:
    rows = "".join(
        f"<li style=\"margin:8px 0\"><b>{_esc(name)}</b>"
        f"<div style=\"color:#d2483a;font-size:12px;margin-top:2px\">{_esc(error)}</div></li>"
        for name, error in failures
    )
    return (
        "<html><body style=\"font-family:'Pretendard','Malgun Gothic',sans-serif;color:#232220;max-width:640px;margin:0 auto\">"
        "<h2 style=\"color:#d2483a\">FeedWatch 크롤링 실패 알림</h2>"
        "<p style=\"color:#6b6862\">아래 사이트가 연속 3회 이상 실패했습니다. 선택자·쿠키·로그인 설정을 점검하세요.</p>"
        f"<ul style=\"padding-left:18px;list-style:none\">{rows}</ul>"
        "</body></html>"
    )


def _filter_for_user(items: list[Item], user: User) -> list[Item]:
    """고른 사이트의 글만 받는다. 아무것도 고르지 않았으면 알림을 보내지 않는다.
    (예전에는 '비어 있으면 전체'였으나, 원치 않는 알림이 오는 쪽이 더 나쁘다고 판단해 바꿨다.)"""
    sources = user.notify_sources or []
    if not sources:
        return []
    return [item for item in items if item.source_id in sources]


def _subject(items: list[Item]) -> str:
    names: list[str] = []
    for item in items:
        if item.source_name not in names:
            names.append(item.source_name)
    if len(names) == 1:
        return f"[FeedWatch] {names[0]} 새 글 {len(items)}건"
    return f"[FeedWatch] {names[0]} 외 {len(names) - 1}곳 새 글 {len(items)}건"


def notify_new_items(
    settings: Settings,
    users: list[User],
    items: list[Item],
    group_names: dict[str, str] | None = None,
) -> tuple[Path | None, list[str]]:
    """수신자별로 '알림 받을 사이트'만 걸러 보낸다.
    반환값 = (미리보기 파일 경로 또는 None, 실패/안내 메시지 목록)."""
    notes: list[str] = []
    if not items:
        return None, notes
    group_names = group_names or {}
    recipients = [u for u in users if u.notify_email and u.email]
    if not recipients:
        notes.append("이메일 알림을 켠 사용자가 없습니다.")

    targeted = [(u, _filter_for_user(items, u)) for u in recipients]
    targeted = [(u, mine) for u, mine in targeted if mine]
    if recipients and not targeted:
        notes.append("새 글은 있으나 그 사이트를 '알림 받을 사이트'로 고른 사람이 없습니다.")

    if targeted and settings.email_provider in {"gmail", "smtp"}:
        sent_any = False
        for user, mine in targeted:
            ok, reason = _send(settings, [user.email], _subject(mine), build_email_html(mine, group_names))
            if ok:
                sent_any = True
            else:
                notes.append(f"{user.email} 발송 실패 — {reason}")
        if sent_any and not notes:
            return None, notes
    elif targeted:
        notes.append(f"발송 방식이 '{settings.email_provider or '미설정'}'이라 실제 발송은 하지 않았습니다(미리보기만 생성).")

    preview = ROOT_DIR / "data" / "last_email_preview.html"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(build_email_html(items, group_names), encoding="utf-8")
    return preview, notes


def notify_failures(settings: Settings, users: list[User], failures: list[tuple[str, str]]) -> Path | None:
    """Alert admins about sources that crossed the consecutive-failure threshold."""
    if not failures:
        return None
    admins = [u for u in users if u.role == "admin" and u.notify_email and u.email]
    subject = f"[FeedWatch] 크롤링 실패 {len(failures)}건"
    html_body = build_failure_html(failures)

    if admins and settings.email_provider in {"gmail", "smtp"}:
        # 실패 알림은 '알림 받을 사이트' 설정과 무관하게 관리자 전원에게 보낸다.
        if any(_send(settings, [u.email], subject, html_body)[0] for u in admins):
            return None

    preview = ROOT_DIR / "data" / "last_failure_preview.html"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(html_body, encoding="utf-8")
    return preview


def _send(settings: Settings, recipients: list[str], subject: str, html_body: str) -> tuple[bool, str]:
    """(성공여부, 실패이유). 실패 이유를 절대 삼키지 않는다 —
    예전에는 예외를 통째로 무시해서 '메일이 왜 안 오는지' 알 방법이 없었다."""
    if settings.email_provider == "gmail":
        try:
            if _send_gmail(settings, recipients, subject, html_body):
                return True, ""
            return False, "Gmail API 설정 파일이 없거나 관련 패키지가 설치되지 않았습니다."
        except Exception as exc:
            return False, f"Gmail: {type(exc).__name__}: {exc}"
    if settings.email_provider == "smtp":
        if not settings.smtp_host:
            return False, "SMTP_HOST가 비어 있습니다."
        try:
            _send_smtp(settings, recipients, subject, html_body)
            return True, ""
        except Exception as exc:
            return False, f"SMTP({settings.smtp_host}:{settings.smtp_port}) {type(exc).__name__}: {exc}"
    return False, f"이메일 발송 방식이 '{settings.email_provider or '미설정'}'이라 실제 발송을 하지 않았습니다."


def _send_smtp(settings: Settings, recipients: list[str], subject: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    # 465는 처음부터 TLS(SMTPS), 그 외에는 서버가 STARTTLS를 지원할 때만 승격한다.
    # 예전에는 무조건 starttls()를 불러서, 465를 쓰거나 STARTTLS가 없는 서버에서는 항상 실패했다.
    if settings.smtp_port == 465:
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    with connection as server:
        server.ehlo()
        if settings.smtp_port != 465 and server.has_extn("starttls"):
            server.starttls()
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(message["From"], recipients, message.as_string())


def _send_gmail(settings: Settings, recipients: list[str], subject: str, html_body: str) -> bool:
    if not settings.gmail_credentials.exists():
        return False
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ModuleNotFoundError:
        return False

    scopes = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None
    if settings.gmail_token.exists():
        creds = Credentials.from_authorized_user_file(str(settings.gmail_token), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(settings.gmail_credentials), scopes)
            creds = flow.run_local_server(port=0)
        settings.gmail_token.write_text(creds.to_json(), encoding="utf-8")

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True
