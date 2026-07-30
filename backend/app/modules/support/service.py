"""SupportService — ticket/reply lifecycle for workspace users and super-admins."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.support.models import SupportAttachment, SupportTicket, SupportTicketReply


class SupportError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SupportService:
    def __init__(self, session: Session):
        self.s = session

    def create_ticket(
        self,
        workspace_id,
        user_id,
        title: str,
        body: str,
        category: str = "other",
    ) -> SupportTicket:
        ticket = SupportTicket(
            workspace_id=uuid.UUID(str(workspace_id)),
            user_id=uuid.UUID(str(user_id)),
            title=title.strip(),
            body=body.strip(),
            category=category.strip().lower(),
            status="open",
        )
        self.s.add(ticket)
        self.s.commit()
        return ticket

    def list_tickets(
        self, workspace_id, user_id, *, is_superadmin: bool = False
    ) -> list[SupportTicket]:
        ws = uuid.UUID(str(workspace_id))
        stmt = select(SupportTicket).where(SupportTicket.workspace_id == ws)
        if not is_superadmin:
            stmt = stmt.where(SupportTicket.user_id == uuid.UUID(str(user_id)))
        stmt = stmt.order_by(SupportTicket.created_at.desc())
        return list(self.s.scalars(stmt))

    def get_ticket(
        self, ticket_id, workspace_id, user_id, *, is_superadmin: bool = False
    ) -> SupportTicket | None:
        ticket = self.s.scalar(
            select(SupportTicket).where(
                SupportTicket.id == uuid.UUID(str(ticket_id)),
                SupportTicket.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if ticket is None:
            return None
        if not is_superadmin and ticket.user_id != uuid.UUID(str(user_id)):
            return None
        return ticket

    def add_reply(
        self,
        ticket_id,
        workspace_id,
        user_id,
        body: str,
        *,
        is_superadmin: bool = False,
    ) -> SupportTicketReply:
        ticket = self.get_ticket(ticket_id, workspace_id, user_id, is_superadmin=is_superadmin)
        if ticket is None:
            raise SupportError("ticket_not_found")
        if ticket.status == "closed":
            raise SupportError("ticket_closed")
        reply = SupportTicketReply(
            workspace_id=ticket.workspace_id,
            ticket_id=ticket.id,
            user_id=uuid.UUID(str(user_id)),
            body=body.strip(),
        )
        self.s.add(reply)
        ticket.updated_at = datetime.now(UTC)
        self.s.commit()
        return reply

    def set_status(
        self,
        ticket_id,
        workspace_id,
        status: str,
    ) -> SupportTicket:
        if status not in {"open", "in_progress", "resolved", "closed"}:
            raise SupportError("invalid_status")
        ticket = self.s.scalar(
            select(SupportTicket).where(
                SupportTicket.id == uuid.UUID(str(ticket_id)),
                SupportTicket.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if ticket is None:
            raise SupportError("ticket_not_found")
        ticket.status = status
        ticket.updated_at = datetime.now(UTC)
        self.s.commit()
        return ticket

    def add_attachment(
        self,
        ticket_id,
        workspace_id,
        user_id,
        storage_key: str,
        filename: str,
        content_type: str,
        *,
        is_superadmin: bool = False,
    ) -> SupportAttachment:
        ticket = self.get_ticket(ticket_id, workspace_id, user_id, is_superadmin=is_superadmin)
        if ticket is None:
            raise SupportError("ticket_not_found")
        att = SupportAttachment(
            workspace_id=ticket.workspace_id,
            ticket_id=ticket.id,
            storage_key=storage_key,
            filename=filename,
            content_type=content_type,
        )
        self.s.add(att)
        self.s.commit()
        return att

    def list_replies(
        self, ticket_id, workspace_id, user_id, *, is_superadmin: bool = False
    ) -> list[SupportTicketReply]:
        ticket = self.get_ticket(ticket_id, workspace_id, user_id, is_superadmin=is_superadmin)
        if ticket is None:
            raise SupportError("ticket_not_found")
        return list(
            self.s.scalars(
                select(SupportTicketReply)
                .where(
                    SupportTicketReply.ticket_id == ticket.id,
                    SupportTicketReply.workspace_id == ticket.workspace_id,
                )
                .order_by(SupportTicketReply.created_at.asc())
            )
        )
