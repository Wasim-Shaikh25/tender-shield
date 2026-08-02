"""Credential-gated notification adapters (SES/MSG91). Each adapter degrades to
console logging when credentials are absent, so dev/test never needs live keys.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.modules.notifications.sender import ConsoleSender, Message, Sender

logger = logging.getLogger(__name__)


class SesSender:
    """AWS SES email adapter; falls back to console when credentials are missing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        if settings.ses_access_key_id and settings.ses_secret_access_key and settings.email_from:
            try:
                import boto3

                self._client = boto3.client(
                    "ses",
                    region_name=settings.ses_region or "us-east-1",
                    aws_access_key_id=settings.ses_access_key_id.get_secret_value(),
                    aws_secret_access_key=settings.ses_secret_access_key.get_secret_value(),
                )
            except Exception as exc:
                logger.warning("ses failed to initialise: %s", exc)

    def send(self, message: Message) -> bool:
        if message.channel != "email" or not self._client:
            logger.info("[ses-fallback] %s to %s: %s", message.channel, message.to, message.subject)
            return True
        try:
            self._client.send_email(
                Source=self.settings.email_from,
                Destination={"ToAddresses": [message.to]},
                Message={
                    "Subject": {"Data": message.subject},
                    "Body": {"Text": {"Data": message.body}},
                },
            )
            return True
        except Exception as exc:
            logger.exception("ses send failed: %s", exc)
            return False


class Msg91Sender:
    """MSG91 SMS/WhatsApp adapter for India-first delivery (Doc §11.7)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._auth = settings.msg91_auth_key.get_secret_value() if settings.msg91_auth_key else None

    def send(self, message: Message) -> bool:
        if message.channel not in ("sms", "whatsapp") or not self._auth:
            logger.info(
                "[msg91-fallback] %s to %s: %s", message.channel, message.to, message.subject
            )
            return True
        try:
            import httpx

            payload = {
                "authkey": self._auth,
                "mobiles": message.to,
                "message": f"{message.subject}\n{message.body}",
                "sender": self.settings.msg91_sender_id or "TENDER",
                "route": "4" if message.channel == "whatsapp" else "4",
                "DLT_TE_ID": "0",
            }
            r = httpx.post("https://api.msg91.com/api/v5/flow/", json=payload, timeout=30)
            return r.status_code in (200, 202)
        except Exception as exc:
            logger.exception("msg91 send failed: %s", exc)
            return False


class ResendSender:
    """Resend email adapter; falls back to console when credentials are missing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._api_key = (
            settings.resend_api_key.get_secret_value() if settings.resend_api_key else None
        )

    def send(self, message: Message) -> bool:
        if message.channel != "email" or not self._api_key:
            logger.info(
                "[resend-fallback] %s to %s: %s",
                message.channel,
                message.to,
                message.subject,
            )
            return True
        try:
            import httpx

            r = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.settings.email_from,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.body,
                },
                timeout=30,
            )
            return r.status_code in (200, 202)
        except Exception as exc:
            logger.exception("resend send failed: %s", exc)
            return False


def build_sender(settings: Settings) -> Sender:
    """Pick the richest configured sender; default to console."""
    if settings.ses_access_key_id and settings.ses_secret_access_key:
        return SesSender(settings)
    if settings.resend_api_key:
        return ResendSender(settings)
    if settings.msg91_auth_key:
        return Msg91Sender(settings)
    return ConsoleSender()
