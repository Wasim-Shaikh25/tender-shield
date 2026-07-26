"""Ingestion-owned tables (Doc §3.2). Opportunity is the shared aggregate root
other modules reference by ID. Both tables are org-scoped (RLS)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class Opportunity(Base, WorkspaceScopedMixin):
    _tablename_ = "opportunities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    employer: Mapped[str | None] = mapped_column(String, nullable=True)
    employer_family: Mapped[str | None] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    contract_form: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="reviewing")
    rulepack_version: Mapped[str | None] = mapped_column(String, nullable=True)
    submission_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clarification_due: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Document(Base, WorkspaceScopedMixin):
    _tablename_ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False, default="other")
    filename: Mapped[str] = mapped_column(String, nullable=False)
    s3_key: Mapped[str] = mapped_column(String, nullable=False, default="")
    sha256: Mapped[str] = mapped_column(String, nullable=False, default="")
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    supersedes: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id"), nullable=True
    )
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Deadline(Base, WorkspaceScopedMixin):
    _tablename_ = "deadlines"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DocChunk(Base, WorkspaceScopedMixin):
    _tablename_ = "doc_chunks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    text: Mapped[str] = mapped_column(String, nullable=False)


class Clause(Base, WorkspaceScopedMixin):
    _tablename_ = "clauses"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clause_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    heading: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cross_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
