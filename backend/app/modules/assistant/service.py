"""AssistantService — grounded, tool-first Q&A over one opportunity (Doc §8).

Recognized intents (deadlines, findings, missing docs, rule-pack lookup) are
answered DETERMINISTICALLY from tool results with citations, so they work with
no API key. Off-topic questions are refused. Free-form questions are answered by
an injected LLM agent only when configured — and even then, only from tool
results (grounded-only).

TS-069 adds conversation/session persistence and an SSE `/chat` stream endpoint.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select

from app.core.db import bind_workspace_context
from app.modules.assistant import tools
from app.modules.assistant.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

_SEVERITIES = {"critical", "high", "medium", "low"}
_DASHBOARD_KEYWORDS = {
    "dashboard",
    "chart",
    "diagram",
    "mindmap",
    "mind map",
    "graph",
    "kpi",
    "visual",
    "visualize",
    "visualisation",
    "visualization",
    "risk severity",
    "deadline timeline",
    "boq defect",
    "bid readiness",
}
_REFUSAL = (
    "I can only help with this workspace's tenders — deadlines, risk findings, "
    "BOQ defects, missing documents, and the rule-pack. Ask me e.g. "
    '"what are the critical risks?" or "list the deadlines".'
)


class AssistantService:
    def __init__(
        self,
        session,
        *,
        ingestion_factory=None,
        findings_factory=None,
        loader=None,
        agent=None,
        workspace_factory=None,
        plan_dashboard_factory=None,
    ):
        self.s = session
        self._ing = ingestion_factory
        self._find = findings_factory
        self._loader = loader
        self._agent = agent
        self._workspace_factory = workspace_factory
        self._plan_dashboard_factory = plan_dashboard_factory

    # ---- workspace binding & access checks ---------------------------------
    def _bind_workspace(self, workspace_id, user_id=None) -> None:
        """Re-bind the RLS GUC to the requested workspace (admin mode needs this)."""
        try:
            bind_workspace_context(self.s, workspace_id, user_id=user_id)
        except Exception:
            logger.exception("Failed to bind workspace context")

    def _can_access(self, workspace_id, user_id) -> bool:
        """Defence-in-depth membership check when auth capability is available."""
        if self._workspace_factory is None:
            return True  # graceful fallback: rely on RLS + principal
        try:
            admin = self._workspace_factory(self.s)
            ws = admin.get(workspace_id)
            if ws is None:
                return False
            if str(ws.owner_id) == str(user_id):
                return True
            return any(
                str(m["user_id"]) == str(user_id)
                for m in admin.list_members(workspace_id)
            )
        except Exception:
            logger.exception("workspace access check failed")
            return False

    def _identity(self, user_id, workspace_id, role, is_superadmin=False) -> dict:
        return {
            "user_id": str(user_id),
            "workspace_id": str(workspace_id),
            "role": role,
            "is_superadmin": bool(is_superadmin),
        }

    # ---- sessions & history ------------------------------------------------
    def create_session(self, workspace_id, opportunity_id, title: str | None = None) -> ChatSession:
        sess = ChatSession(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            title=title,
        )
        self.s.add(sess)
        self.s.commit()
        return sess

    def list_sessions(self, workspace_id, opportunity_id=None) -> list[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.workspace_id == uuid.UUID(str(workspace_id)))
        if opportunity_id:
            stmt = stmt.where(ChatSession.opportunity_id == uuid.UUID(str(opportunity_id)))
        return list(self.s.scalars(stmt.order_by(ChatSession.updated_at.desc())))

    def get_session(self, workspace_id, session_id):
        return self.s.scalar(
            select(ChatSession).where(
                ChatSession.id == uuid.UUID(str(session_id)),
                ChatSession.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )

    def get_messages(self, workspace_id, session_id) -> list[ChatMessage]:
        return list(
            self.s.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == uuid.UUID(str(session_id)),
                    ChatMessage.workspace_id == uuid.UUID(str(workspace_id)),
                )
                .order_by(ChatMessage.created_at)
            )
        )

    def _add_message(self, workspace_id, session_id, role: str, answer: dict) -> ChatMessage:
        msg = ChatMessage(
            workspace_id=uuid.UUID(str(workspace_id)),
            session_id=uuid.UUID(str(session_id)),
            role=role,
            content=answer["answer"],
            message_type=answer.get("type", "text"),
            dashboard=answer.get("dashboard"),
            grounded=answer.get("grounded", True),
            source=answer.get("source"),
            citations=answer.get("citations", []),
        )
        self.s.add(msg)
        self.s.commit()
        return msg

    def answer_and_store(
        self,
        workspace_id,
        session_id,
        opportunity_id,
        message: str,
        *,
        identity: dict | None = None,
    ) -> dict:
        user_msg = ChatMessage(
            workspace_id=uuid.UUID(str(workspace_id)),
            session_id=uuid.UUID(str(session_id)),
            role="user",
            content=message,
            grounded=True,
            source="user",
        )
        self.s.add(user_msg)
        self.s.commit()
        answer = self.answer(workspace_id, opportunity_id, message, identity=identity)
        self._add_message(workspace_id, session_id, "assistant", answer)
        return answer

    def answer_stream(
        self,
        workspace_id,
        session_id,
        opportunity_id,
        message: str,
        *,
        identity: dict | None = None,
    ):
        """Generator of SSE `data:` lines for the chat response."""
        user_msg = ChatMessage(
            workspace_id=uuid.UUID(str(workspace_id)),
            session_id=uuid.UUID(str(session_id)),
            role="user",
            content=message,
            grounded=True,
            source="user",
        )
        self.s.add(user_msg)
        self.s.commit()

        answer = self.answer(workspace_id, opportunity_id, message, identity=identity)
        payload = json.dumps(answer)
        yield f"data: {payload}\n\n"

        self._add_message(workspace_id, session_id, "assistant", answer)
        yield "event: done\ndata: {}\n\n"

    # ---- answer logic ------------------------------------------------------
    def answer(
        self,
        workspace_id,
        opportunity_id,
        message: str,
        *,
        identity: dict | None = None,
    ) -> dict:
        self._bind_workspace(workspace_id, user_id=identity.get("user_id") if identity else None)
        if identity and not identity.get("is_superadmin"):
            if not self._can_access(workspace_id, identity["user_id"]):
                return {"type": "text", "answer": _REFUSAL, "grounded": True, "source": "refusal"}

        m = message.lower()

        if any(w in m for w in _DASHBOARD_KEYWORDS):
            return self._dashboard(workspace_id, opportunity_id, message, identity=identity)

        if any(w in m for w in ("deadline", "due", "submission", "pre-bid", "clarification cut")):
            return self._deadlines(workspace_id, opportunity_id)
        if any(w in m for w in ("missing", "document checklist", "which docs", "what documents")):
            return self._missing(workspace_id, opportunity_id)
        if any(
            w in m
            for w in (
                "risk",
                "finding",
                "clause",
                "ld",
                "escalation",
                "termination",
                "payment",
                "defect",
                "critical",
                "severity",
            )
        ):
            return self._findings(workspace_id, opportunity_id, m)

        # Not a recognized grounded intent → defer to the LLM if configured,
        # else refuse (grounded-only, Doc §8).
        if self._agent is not None:
            context = {
                "deadlines": tools.list_deadlines(self._ing, self.s, workspace_id, opportunity_id),
                "findings": tools.filter_findings(self._find, self.s, workspace_id, opportunity_id),
            }
            reply = self._agent.answer(message, context, identity=identity)
            return {"type": "text", "answer": reply, "grounded": True, "source": "llm"}
        return {"type": "text", "answer": _REFUSAL, "grounded": True, "source": "refusal"}

    def admin_answer(
        self,
        workspace_id,
        opportunity_id,
        message: str,
        *,
        identity: dict,
    ) -> dict:
        """Super-admin research mode: rebind to the requested workspace and answer.

        The caller is already verified as super-admin by the router; this method
        just ensures the database context matches the explicit workspace.
        """
        self._bind_workspace(workspace_id, user_id=identity.get("user_id"))
        return self.answer(workspace_id, opportunity_id, message, identity=identity)

    # ---- deterministic intent handlers -------------------------------------
    def _dashboard(
        self, workspace_id, opportunity_id, message: str, *, identity: dict | None = None
    ) -> dict:
        if self._plan_dashboard_factory is None:
            return {
                "type": "text",
                "answer": (
                    "Dashboard generation is not available right now — "
                    "the analytics module is disabled."
                ),
                "grounded": True,
                "source": "refusal",
            }
        dashboard = self._plan_dashboard_factory(
            self.s, workspace_id, opportunity_id, message, identity=identity
        )
        return {
            "type": "dashboard",
            "answer": f"Generated a {dashboard.get('title', 'dashboard')} for this tender.",
            "dashboard": dashboard,
            "grounded": True,
            "source": "llm",
        }

    def _deadlines(self, workspace_id, opportunity_id) -> dict:
        rows = tools.list_deadlines(self._ing, self.s, workspace_id, opportunity_id)
        if not rows:
            return {
                "type": "text",
                "answer": "No deadlines have been extracted yet.",
                "grounded": True,
                "source": "tool",
            }
        lines = [
            f"- {r['kind']}: {r['due_at'] or 'date not parsed'} [p{r['page']}]"
            f"{' (confirmed)' if r['confirmed'] else ''}"
            for r in rows
        ]
        return {
            "type": "text",
            "answer": "Deadlines for this tender:\n" + "\n".join(lines),
            "grounded": True,
            "source": "tool",
            "citations": [f"p{r['page']}" for r in rows],
        }

    def _missing(self, workspace_id, opportunity_id) -> dict:
        rep = tools.missing_docs(self._ing, self.s, workspace_id, opportunity_id)
        if rep["missing"]:
            names = ", ".join(k.upper() for k in rep["missing"])
            ans = f"Missing expected documents: {names}."
        else:
            ans = "All expected documents are present."
        return {"type": "text", "answer": ans, "grounded": True, "source": "tool"}

    def _findings(self, workspace_id, opportunity_id, m: str) -> dict:
        severity = next((s for s in _SEVERITIES if s in m), None)
        rows = tools.filter_findings(
            self._find, self.s, workspace_id, opportunity_id, severity=severity
        )
        if not rows:
            scope = f"{severity} " if severity else ""
            return {
                "type": "text",
                "answer": f"No {scope}findings on this tender yet — run the risk review "
                "and BOQ check first.",
                "grounded": True,
                "source": "tool",
            }
        lines = [
            f"- [{r['severity']}] {r['category']}: {r['title']}"
            + (f" [p{r['page']}]" if r["page"] else "")
            for r in rows
        ]
        header = f"{severity.capitalize()} findings:" if severity else "Findings on this tender:"
        return {
            "type": "text",
            "answer": header + "\n" + "\n".join(lines),
            "grounded": True,
            "source": "tool",
            "citations": [f"p{r['page']}" for r in rows if r["page"]],
        }
