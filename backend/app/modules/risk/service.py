"""RiskService — runs rule-pack patterns over an opportunity's clauses.

Consumes ingestion (clauses/opportunity) and rulepacks (patterns) purely via
registry capabilities — no imports of those modules. The classifier is injected
so the LLM boundary is swappable."""

from __future__ import annotations

from app.core.config import Settings
from app.core.contracts.findings import Finding
from app.core.provenance import document_set_hash, get_engine_version
from app.modules.risk.classifier import NullClassifier
from app.modules.risk.engine import run_patterns


class RiskService:
    PRODUCER = "risk"

    def __init__(
        self,
        session,
        *,
        ingestion_factory=None,
        loader=None,
        classifier=None,
        store_factory=None,
        workspace_factory=None,
        pack_id="in-works",
        settings: Settings | None = None,
    ):
        self.session = session
        self._ingestion_factory = ingestion_factory
        self._loader = loader
        self._classifier = classifier or NullClassifier()
        self._store_factory = store_factory
        self._workspace_factory = workspace_factory
        self._pack_id = pack_id
        self._settings = settings or Settings()

    def _is_paying(self, workspace_id) -> bool:
        if not self._workspace_factory:
            return False
        admin = self._workspace_factory(self.session)
        owner_id = admin.get_owner(workspace_id)
        if owner_id is None:
            return False
        return admin.is_paying(owner_id)

    def _clauses(self, workspace_id, opportunity_id) -> list[dict]:
        if not self._ingestion_factory:
            return []
        svc = self._ingestion_factory(self.session)
        return [
            {
                "id": str(c.id),
                "clause_ref": c.clause_ref,
                "text": c.text,
                "page_from": c.page_from,
                "document_id": str(c.document_id),
            }
            for c in svc.list_clauses(workspace_id, opportunity_id)
        ]

    def _opp_facts(self, workspace_id, opportunity_id) -> dict:
        if not self._ingestion_factory:
            return {}
        opp = self._ingestion_factory(self.session).get_opportunity(workspace_id, opportunity_id)
        return {"employer_family": opp.employer_family} if opp else {}

    def _document_hash(self, workspace_id, opportunity_id) -> str:
        if not self._ingestion_factory:
            return ""
        docs = self._ingestion_factory(self.session).list_documents(workspace_id, opportunity_id)
        return document_set_hash([d.sha256 for d in docs])

    def _pack_for_opportunity(self, opportunity_id) -> object | None:
        if not self._loader:
            return None
        return self._loader.get_combined_pack_for_opportunity(
            self.session, opportunity_id
        ) or self._loader.get_pack(self._pack_id)

    def _rulepack_version(self, opportunity_id) -> str:
        if not self._loader:
            return "unknown"
        pack = self._pack_for_opportunity(opportunity_id)
        return pack.meta.version if pack else "unknown"

    def run_opportunity(self, workspace_id, opportunity_id) -> list[Finding]:
        if not self._loader:
            return []
        pack = self._pack_for_opportunity(opportunity_id)
        paying = self._is_paying(workspace_id)
        # Paying workspaces see only validated patterns unless the beta/disclaimer
        # flag is explicitly enabled (TS-125). When enabled, unvalidated patterns
        # are still tagged with a disclaimer so users know they are unverified.
        validated_only = paying and not self._settings.beta_unvalidated
        patterns = list(pack.patterns.values()) if pack else []
        if pack and not validated_only:
            patterns = [p for p in patterns if p.confidence == "validated" or not validated_only]
        # Tag unvalidated patterns with a disclaimer whenever they may appear in
        # the result set (free workspaces or beta-enabled paying workspaces).
        disclaimer = None
        if not paying or self._settings.beta_unvalidated:
            disclaimer = (
                "This risk pattern has not been QS-validated; "
                "treat as a beta suggestion and verify independently."
            )
        clauses = self._clauses(workspace_id, opportunity_id)
        facts = self._opp_facts(workspace_id, opportunity_id)
        provenance = {
            "rulepack_version": self._rulepack_version(opportunity_id),
            "document_hash": self._document_hash(workspace_id, opportunity_id),
            "engine_version": get_engine_version(),
        }
        findings = run_patterns(
            patterns,
            clauses,
            self._classifier,
            facts,
            disclaimer=disclaimer,
            provenance=provenance,
        )
        # Persist through the findings store when available (idempotent re-run);
        # if the findings module is disabled, still return the in-memory result.
        if self._store_factory is not None:
            self._store_factory(self.session).replace_for_producer(
                workspace_id, opportunity_id, self.PRODUCER, findings
            )
        return findings
