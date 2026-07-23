"""Pluggable notification senders. ConsoleSender is the dev/test backend and
records what it "sent"; SES/Resend (email) and MSG91 (SMS/WhatsApp) adapters
plug in behind the same interface (TS-035, need creds). The deadline-alert path
is the most safety-critical in the product (Doc §11.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Message:
    channel: str  # email | whatsapp | sms
    to: str
    subject: str
    body: str


class Sender(Protocol):
    def send(self, message: Message) -> bool: ...


class ConsoleSender:
    """Records into an in-memory outbox; delivery is always reported successful."""

    def __init__(self) -> None:
        self.outbox: list[Message] = []

    def send(self, message: Message) -> bool:
        self.outbox.append(message)
        return True
