"""RiskService — runs rule-pack patterns over an opportunity's clauses.

Consumes ingestion (clauses/opportunity) and rulepacks (patterns) purely via
registry capabilities — no imports of those modules. The classifier is injected
so the LLM boundary is swappable."""

from __future__ import annotations

from app.core.contracts.findings import Finding
from app.modules.risk.classifier import NullClassifier
from app.modules.risk.engine import run_patterns


class RiskService:
    PRODUCER = "risk"

    def __init__(self, session, *, ingestion_factory=None, loader=None, classifier=None,
                 store_factory=None, pack_id="in-works"):
        self.session = session
        self._ingestion_factory = ingestion_factory
        self._loader = loader
        self._classifier = classifier or NullClassifier()
        self._store_factory = store_factory
        self._pack_id = pack_id

    def _clauses(self, org_id, opportunity_id) -> list[dict]:
        if not self._ingestion_factory:
            return []
        svc = self._ingestion_factory(self.session)
        return [
            {
                "id": str(c.id),
                "clause_ref": c.clause_ref,
                "text": c.text,
                "page_from": c.page_from,
            }
            for c in svc.list_clauses(org_id, opportunity_id)
        ]

    def _opp_facts(self, org_id, opportunity_id) -> dict:
        if not self._ingestion_factory:
            return {}
        opp = self._ingestion_factory(self.session).get_opportunity(org_id, opportunity_id)
        return {"employer_family": opp.employer_family} if opp else {}

    def run_opportunity(self, org_id, opportunity_id) -> list[Finding]:
        if not self._loader:
            return []
        patterns = self._loader.list_patterns(self._pack_id)
        clauses = self._clauses(org_id, opportunity_id)
        facts = self._opp_facts(org_id, opportunity_id)
        findings = run_patterns(patterns, clauses, self._classifier, facts)
        # Persist through the findings store when available (idempotent re-run);
        # if the findings module is disabled, still return the in-memory result.
        if self._store_factory is not None:
            self._store_factory(self.session).replace_for_producer(
                org_id, opportunity_id, self.PRODUCER, findings
            )
        return findings
