"""SMTP email helper."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, Tuple

import config

LOGGER = logging.getLogger(__name__)
Attachment = Tuple[str, bytes, str]


class EmailClient:
    """Simple SMTP client for sending Trade Buddy reports."""

    def __init__(self) -> None:
        self.host = config.SMTP_HOST
        self.port = config.SMTP_PORT
        self.username = config.SMTP_USERNAME
        self.password = config.SMTP_PASSWORD
        self.sender = config.EMAIL_FROM
        self.recipient = config.EMAIL_TO

    def send_email(
        self,
        *,
        subject: str,
        body_text: str,
        html_body: str | None = None,
        attachments: Iterable[Attachment] | None = None,
    ) -> None:
        """Send an email with optional attachments and HTML alternative."""
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = self.recipient
        message["Subject"] = subject
        message.set_content(body_text)
        if html_body:
            message.add_alternative(html_body, subtype="html")
        for attachment in attachments or []:
            filename, data, mime_type = attachment
            maintype, subtype = mime_type.split("/", 1)
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        LOGGER.info("Sending email '%s'", subject)
        with smtplib.SMTP(self.host, self.port, timeout=30) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(message)
