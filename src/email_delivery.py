from __future__ import annotations

import mimetypes
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_EMAIL = "jongeunshin95@kbfg.com"


@dataclass
class SMTPSettings:
    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    security: str = "starttls"
    timeout_seconds: int = 30


def build_email_message(
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    attachments: Iterable[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(
        "Daily Insight 리포트가 생성되었습니다. HTML 메일을 지원하는 환경에서 확인해 주세요."
    )
    message.add_alternative(html_body, subtype="html")

    for attachment in attachments:
        mime_type, _ = mimetypes.guess_type(str(attachment))
        main_type, sub_type = (
            mime_type.split("/", 1)
            if mime_type
            else ("application", "octet-stream")
        )
        message.add_attachment(
            attachment.read_bytes(),
            maintype=main_type,
            subtype=sub_type,
            filename=attachment.name,
        )
    return message


def send_email(
    settings: SMTPSettings,
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    attachments: Iterable[Path],
) -> None:
    if not settings.host:
        raise ValueError("SMTP_HOST가 비어 있습니다.")
    if not sender or not recipient:
        raise ValueError("발신자와 수신자 이메일을 입력해 주세요.")

    message = build_email_message(
        sender,
        recipient,
        subject,
        html_body,
        attachments,
    )
    security = settings.security.lower()
    context = ssl.create_default_context()

    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(
                settings.host,
                settings.port,
                timeout=settings.timeout_seconds,
                context=context,
            ) as smtp:
                _login_if_configured(smtp, settings)
                smtp.send_message(message)
            return

        with smtplib.SMTP(
            settings.host,
            settings.port,
            timeout=settings.timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            if security == "starttls":
                smtp.starttls(context=context)
                smtp.ehlo()
            _login_if_configured(smtp, settings)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP 인증에 실패했습니다. Gmail 주소와 일반 비밀번호가 아닌 "
            "16자리 앱 비밀번호를 확인해 주세요."
        ) from exc
    except (
        ConnectionResetError,
        ConnectionAbortedError,
        BrokenPipeError,
        smtplib.SMTPServerDisconnected,
    ) as exc:
        raise RuntimeError(
            "SMTP 서버가 연결을 강제로 종료했습니다. 현재 네트워크에서 외부 SMTP "
            "포트가 차단됐을 가능성이 큽니다. 다른 네트워크에서 다시 시도하거나 "
            "PDF를 내려받아 Gmail 웹에서 직접 첨부해 주세요."
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError(
            "SMTP 서버 연결 시간이 초과되었습니다. 네트워크 방화벽과 SMTP Host, "
            "Port, 보안 방식을 확인해 주세요."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"SMTP 서버 {settings.host}:{settings.port}에 연결하지 못했습니다. "
            "네트워크 또는 방화벽 설정을 확인해 주세요."
        ) from exc


def email_as_bytes(
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    attachments: Iterable[Path],
) -> bytes:
    return build_email_message(
        sender,
        recipient,
        subject,
        html_body,
        attachments,
    ).as_bytes()


def _login_if_configured(
    smtp: smtplib.SMTP,
    settings: SMTPSettings,
) -> None:
    if settings.username:
        if not settings.password:
            raise ValueError("SMTP_USERNAME은 있지만 SMTP_PASSWORD가 비어 있습니다.")
        smtp.login(settings.username, settings.password)
