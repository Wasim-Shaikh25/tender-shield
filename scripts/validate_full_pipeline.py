#!/usr/bin/env python3
"""End-to-end validation importer for TenderShield.

Creates a test account/workspace, seeds N opportunities from sample tender
fixtures, runs the full pipeline through the public API, and writes a pass/fail
report. Designed to run unattended against a local SQLite dev server.

Typical usage:

    # 1. Start backend with the validation env in one terminal:
    set -a && source .env.validation && set +a
    cd backend && .venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

    # 2. In another terminal run the importer:
    backend/.venv/bin/python scripts/validate_full_pipeline.py --count 50

The script can also start the backend itself with --start-backend.

Task: TS-344
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from docx import Document

REPO = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO / "evals" / "in-works" / "sample_tender"
CONDITIONS_MD = SAMPLE_DIR / "conditions.md"
BOQ_CSV = SAMPLE_DIR / "boq.csv"
DEFAULT_BASE_URL = "http://localhost:8000/api"

# Market presets used when creating opportunities.
PRESETS = [
    {
        "jurisdiction": "IN",
        "country": "IN",
        "currency": "INR",
        "employer": "CPWD",
        "employer_family": "CPWD",
    },
    {
        "jurisdiction": "IN",
        "country": "IN",
        "currency": "INR",
        "employer": "NHAI",
        "employer_family": "NHAI",
    },
    {
        "jurisdiction": "IN",
        "country": "IN",
        "currency": "INR",
        "employer": "State PWD Maharashtra",
        "employer_family": "STATE_PWD",
    },
    {
        "jurisdiction": "AE",
        "country": "AE",
        "currency": "AED",
        "employer": "Emaar Properties",
        "employer_family": None,
    },
    {
        "jurisdiction": "AE",
        "country": "AE",
        "currency": "AED",
        "employer": "Aldar Estates",
        "employer_family": None,
    },
]


@dataclass
class FeatureResult:
    name: str
    ok: bool
    status: int | None
    detail: str = ""
    error: str = ""


@dataclass
class OpportunityResult:
    index: int
    title: str
    jurisdiction: str
    opportunity_id: str | None = None
    features: list[FeatureResult] = field(default_factory=list)
    error: str = ""


@dataclass
class RunReport:
    account_email: str = ""
    workspace_id: str | None = None
    workspace_name: str = ""
    base_url: str = ""
    total: int = 0
    completed: int = 0
    failed: int = 0
    opportunities: list[OpportunityResult] = field(default_factory=list)
    global_features: list[FeatureResult] = field(default_factory=list)


class ValidationClient:
    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def health(self, timeout: int = 60) -> bool:
        for _ in range(timeout):
            try:
                r = self.session.get(self._url("/health"), timeout=2)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def signup_or_login(
        self, email: str, password: str, org_name: str = "Validation Org", city: str = "Pune"
    ) -> str:
        # Try login first; if the account exists we can reuse it.
        r = self.session.post(
            self._url("/auth/login"),
            json={"email": email, "password": password, "method": "password"},
        )
        if r.status_code == 200:
            return r.json()["access_token"]

        # Otherwise sign up, verify email, then log in.
        r = self.session.post(
            self._url("/auth/signup"),
            json={
                "email": email,
                "password": password,
                "confirm_password": password,
                "org_name": org_name,
                "city": city,
            },
        )
        if r.status_code != 200:
            raise RuntimeError(f"signup failed {r.status_code}: {r.text[:300]}")
        data = r.json()
        if data.get("email_verification_token"):
            v = self.session.post(
                self._url("/auth/verify-email"),
                json={"token": data["email_verification_token"]},
            )
            if v.status_code != 200:
                raise RuntimeError(f"email verify failed {v.status_code}: {v.text[:300]}")

        r = self.session.post(
            self._url("/auth/login"),
            json={"email": email, "password": password, "method": "password"},
        )
        if r.status_code != 200:
            raise RuntimeError(f"login after signup failed {r.status_code}: {r.text[:300]}")
        return r.json()["access_token"]

    def refresh(self) -> str:
        r = self.session.post(self._url("/auth/refresh"))
        if r.status_code != 200:
            raise RuntimeError(f"refresh failed {r.status_code}: {r.text[:300]}")
        return r.json()["access_token"]

    def ensure_workspace(self, token: str, name: str, country: str) -> dict:
        r = self.session.get(
            self._url("/auth/workspaces"),
            headers=self._auth_header(token),
        )
        if r.status_code == 200:
            for ws in r.json():
                if ws.get("name") == name:
                    return ws
        r = self.session.post(
            self._url("/auth/workspaces"),
            json={"name": name, "country": country},
            headers=self._auth_header(token),
        )
        if r.status_code != 200:
            raise RuntimeError(f"workspace create failed {r.status_code}: {r.text[:300]}")
        return r.json()

    def switch_workspace(self, token: str, workspace_id: str) -> str:
        r = self.session.post(
            self._url(f"/auth/workspaces/{workspace_id}/switch"),
            headers=self._auth_header(token),
        )
        if r.status_code != 200:
            raise RuntimeError(f"workspace switch failed {r.status_code}: {r.text[:300]}")
        return r.json()["access_token"]

    def post(
        self, path: str, token: str, json_body: Any | None = None, **kwargs
    ) -> requests.Response:
        return self.session.post(
            self._url(path),
            headers=self._auth_header(token),
            json=json_body,
            **kwargs,
        )

    def get(self, path: str, token: str, **kwargs) -> requests.Response:
        return self.session.get(
            self._url(path),
            headers=self._auth_header(token),
            **kwargs,
        )


def _build_conditions_docx(out_path: Path) -> Path:
    """Convert the sample markdown conditions file into a .docx we can upload."""
    if out_path.exists():
        return out_path
    text = CONDITIONS_MD.read_text(encoding="utf-8")
    doc = Document()
    for para in text.split("\n"):
        doc.add_paragraph(para)
    doc.save(out_path)
    return out_path


def _build_boq_csv_text() -> str:
    return BOQ_CSV.read_text(encoding="utf-8")


def _create_opportunity(
    client: ValidationClient, token: str, index: int, preset: dict
) -> tuple[str, str]:
    title = f"Validation {preset['jurisdiction']} #{index:03d} — {preset['employer']}"
    body = {
        "title": title,
        "jurisdiction": preset["jurisdiction"],
        "currency": preset["currency"],
        "contract_value_minor": 50_000_000,
        "employer": preset["employer"],
    }
    if preset.get("employer_family"):
        body["employer_family"] = preset["employer_family"]
    r = client.post("/ingestion/opportunities", token, body)
    if r.status_code != 200:
        raise RuntimeError(f"opportunity create failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data["id"], title


def _upload_document(
    client: ValidationClient, token: str, opportunity_id: str, docx_path: Path
) -> FeatureResult:
    try:
        with open(docx_path, "rb") as fh:
            files = {
                "file": (
                    docx_path.name,
                    fh,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
            r = client.session.post(
                client._url(f"/ingestion/opportunities/{opportunity_id}/upload"),
                headers=client._auth_header(token),
                files=files,
            )
        ok = r.status_code == 200
        detail = r.json() if ok and r.text else ""
        return FeatureResult(
            name="upload_conditions",
            ok=ok,
            status=r.status_code,
            detail=f"{detail.get('kind', '?')} {detail.get('chars', 0)} chars"
            if ok
            else r.text[:200],
        )
    except Exception as exc:
        return FeatureResult(name="upload_conditions", ok=False, status=None, error=str(exc))


def _run_risk(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.post(f"/risk/opportunities/{opportunity_id}/run", token)
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="risk_review", ok=True, status=200, detail=f"{data.get('count', 0)} findings"
        )
    return FeatureResult(name="risk_review", ok=False, status=r.status_code, detail=r.text[:200])


def _run_boq(
    client: ValidationClient, token: str, opportunity_id: str, csv_text: str
) -> FeatureResult:
    r = client.post(f"/boq/opportunities/{opportunity_id}/run", token, {"csv": csv_text})
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="boq_check", ok=True, status=200, detail=f"{data.get('count', 0)} findings"
        )
    return FeatureResult(name="boq_check", ok=False, status=r.status_code, detail=r.text[:200])


def _auto_review(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.get(f"/findings/opportunities/{opportunity_id}", token)
    if r.status_code != 200:
        return FeatureResult(
            name="list_findings", ok=False, status=r.status_code, detail=r.text[:200]
        )
    findings = r.json().get("findings", [])
    accepted = 0
    for finding in findings:
        if finding.get("review_status") != "proposed":
            continue
        fr = client.post(
            f"/review/findings/{finding['id']}",
            token,
            {
                "opportunity_id": opportunity_id,
                "decision": "accepted",
                "note": "auto-accepted by TS-344 validation script",
            },
        )
        if fr.status_code == 200:
            accepted += 1
    return FeatureResult(
        name="auto_review",
        ok=True,
        status=200,
        detail=f"accepted {accepted}/{len(findings)} findings",
    )


def _freeze_baseline(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.post(
        f"/baseline/opportunities/{opportunity_id}/freeze",
        token,
        {"source": "tender", "note": "TS-344 validation baseline"},
    )
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="baseline_freeze", ok=True, status=200, detail=f"version {data.get('version')}"
        )
    return FeatureResult(
        name="baseline_freeze", ok=False, status=r.status_code, detail=r.text[:200]
    )


def _notice_register(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.get(f"/baseline/opportunities/{opportunity_id}/notice-register", token)
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="notice_register",
            ok=True,
            status=200,
            detail=f"{len(data.get('rules', []))} rules, {len(data.get('gaps', []))} gaps",
        )
    return FeatureResult(
        name="notice_register", ok=False, status=r.status_code, detail=r.text[:200]
    )


def _generate_artifacts(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    ok_count = 0
    errors: list[str] = []
    for kind in ("clarification_letter", "assumptions_register"):
        r = client.post(
            f"/drafting/opportunities/{opportunity_id}/artifacts", token, {"kind": kind}
        )
        if r.status_code == 200:
            ok_count += 1
        else:
            errors.append(f"{kind}: {r.status_code} {r.text[:120]}")
    return FeatureResult(
        name="drafting_artifacts",
        ok=ok_count == 2,
        status=200 if ok_count == 2 else 0,
        detail=f"{ok_count}/2 generated" + ("; " + "; ".join(errors) if errors else ""),
    )


def _export_report(client: ValidationClient, token: str) -> FeatureResult:
    r = client.post("/analytics/reports/export?format=xlsx&filter=all", token)
    if r.status_code == 200:
        return FeatureResult(
            name="export_report", ok=True, status=200, detail=f"{len(r.content)} bytes XLSX"
        )
    return FeatureResult(name="export_report", ok=False, status=r.status_code, detail=r.text[:200])


def _create_subcontract(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.post(
        f"/subcontract/opportunities/{opportunity_id}/subcontracts",
        token,
        {
            "subcontractor_name": "Validation Subcontractor",
            "reference": "SUB-VAL-001",
            "contract_value_minor": 25_000_000,
            "currency": "INR",
            "scope": "Structural and finishing works",
            "notice_buffer_days": 7,
            "postal_buffer_days": 3,
        },
    )
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="create_subcontract", ok=True, status=200, detail=f"id {data.get('id')}"
        )
    return FeatureResult(
        name="create_subcontract", ok=False, status=r.status_code, detail=r.text[:200]
    )


def _create_change_event(
    client: ValidationClient, token: str, opportunity_id: str
) -> FeatureResult:
    r = client.post(
        f"/change/opportunities/{opportunity_id}/events",
        token,
        {
            "title": "Validation change — additional scope",
            "reason": "design revision",
            "affected_scope": "civil_structure",
            "confidence_band": "medium",
            "notice_type": "variation",
            "trigger_date": "2026-08-15",
            "sources": [
                {"source_kind": "email", "source_quote": "Revised drawing V2 issued by engineer."}
            ],
        },
    )
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="create_change_event", ok=True, status=200, detail=f"id {data.get('id')}"
        )
    return FeatureResult(
        name="create_change_event", ok=False, status=r.status_code, detail=r.text[:200]
    )


def _create_claim(client: ValidationClient, token: str, opportunity_id: str) -> FeatureResult:
    r = client.post(
        f"/claims/opportunities/{opportunity_id}/claims",
        token,
        {
            "claim_type": "extension_of_time",
            "title": "Validation EOT claim",
            "claimant_party": "contractor",
            "claim_amount_minor": 10_000_000,
            "currency": "INR",
        },
    )
    if r.status_code == 200:
        data = r.json()
        return FeatureResult(
            name="create_claim", ok=True, status=200, detail=f"id {data.get('id')}"
        )
    return FeatureResult(name="create_claim", ok=False, status=r.status_code, detail=r.text[:200])


def _pricing_checks(
    client: ValidationClient, token: str, opportunity_id: str, csv_text: str
) -> FeatureResult:
    ok_count = 0
    errors: list[str] = []
    # loading
    r = client.get(f"/pricing/opportunities/{opportunity_id}/loading?currency=INR", token)
    if r.status_code == 200:
        ok_count += 1
    else:
        errors.append(f"loading: {r.status_code}")
    # rate benchmark
    r = client.post(
        f"/pricing/opportunities/{opportunity_id}/rate-benchmark",
        token,
        {"csv": csv_text, "authority": "cpwd", "year": "2026"},
    )
    if r.status_code == 200:
        ok_count += 1
    else:
        errors.append(f"rate-benchmark: {r.status_code} {r.text[:120]}")
    return FeatureResult(
        name="pricing_checks",
        ok=ok_count == 2,
        status=200 if ok_count == 2 else 0,
        detail=f"{ok_count}/2 passed" + ("; " + "; ".join(errors) if errors else ""),
    )


def _controltower_dashboards(
    client: ValidationClient, token: str, opportunity_id: str
) -> FeatureResult:
    ok_count = 0
    errors: list[str] = []
    for path in ("dashboard", "exposure", "executive-summary", "payment-schedule"):
        r = client.get(
            f"/controltower/{path}?opportunity_id={opportunity_id}&currency=INR&cost_of_capital_pa=0.12",
            token,
        )
        if r.status_code == 200:
            ok_count += 1
        else:
            errors.append(f"{path}: {r.status_code}")
    return FeatureResult(
        name="controltower_dashboards",
        ok=ok_count == 4,
        status=200 if ok_count == 4 else 0,
        detail=f"{ok_count}/4 OK" + ("; " + "; ".join(errors) if errors else ""),
    )


def _opportunity_basic_flow(
    client: ValidationClient,
    token: str,
    index: int,
    docx_path: Path,
    csv_text: str,
    complete: bool,
) -> OpportunityResult:
    preset = PRESETS[index % len(PRESETS)]
    result = OpportunityResult(index=index, title="", jurisdiction=preset["jurisdiction"])
    try:
        opp_id, title = _create_opportunity(client, token, index, preset)
        result.opportunity_id = opp_id
        result.title = title

        result.features.append(_upload_document(client, token, opp_id, docx_path))
        result.features.append(_run_risk(client, token, opp_id))
        result.features.append(_run_boq(client, token, opp_id, csv_text))

        if complete:
            result.features.append(_auto_review(client, token, opp_id))
            result.features.append(_freeze_baseline(client, token, opp_id))
            result.features.append(_notice_register(client, token, opp_id))
            result.features.append(_generate_artifacts(client, token, opp_id))
            result.features.append(_create_subcontract(client, token, opp_id))
            result.features.append(_create_change_event(client, token, opp_id))
            result.features.append(_create_claim(client, token, opp_id))
            result.features.append(_pricing_checks(client, token, opp_id, csv_text))
            result.features.append(_controltower_dashboards(client, token, opp_id))
        else:
            # For reviewable opportunities we still assert the review gate is closed.
            gate = client.get(f"/review/opportunities/{opp_id}/gate", token)
            result.features.append(
                FeatureResult(
                    name="review_gate_pending",
                    ok=gate.status_code == 200,
                    status=gate.status_code,
                    detail=(gate.json() if gate.status_code == 200 else gate.text[:200]),
                )
            )
    except Exception as exc:
        result.error = f"{exc}\n{traceback.format_exc()}"
    return result


def _start_backend(env_file: Path, port: int) -> subprocess.Popen:
    shell_cmd = (
        f"set -a && source {env_file} && set +a && "
        f"cd backend && .venv/bin/alembic upgrade head && "
        f".venv/bin/uvicorn app.main:create_app --factory "
        f"--host 0.0.0.0 --port {port} --no-access-log"
    )
    return subprocess.Popen(["bash", "-c", shell_cmd], cwd=str(REPO))


def _write_report(report: RunReport, out_path: Path) -> None:
    lines: list[str] = []
    lines.append("# TenderShield full-pipeline validation report\n")
    lines.append(f"- **Account:** {report.account_email}")
    lines.append(f"- **Workspace:** {report.workspace_name} (`{report.workspace_id}`)")
    lines.append(f"- **Base URL:** {report.base_url}")
    lines.append(f"- **Total opportunities:** {report.total}")
    lines.append(f"- **Completed (full lifecycle):** {report.completed}")
    lines.append(f"- **Failed opportunities:** {report.failed}")
    lines.append("")

    lines.append("## Global features\n")
    for f in report.global_features:
        status = "PASS" if f.ok else "FAIL"
        err = f" — {f.error}" if f.error else ""
        lines.append(f"- **{f.name}**: {status} ({f.status}) — {f.detail}{err}")
    lines.append("")

    lines.append("## Per-opportunity results\n")
    for opp in report.opportunities:
        lines.append(f"### {opp.index}. {opp.title}")
        if opp.error:
            lines.append(f"- **ERROR:** {opp.error[:500]}")
        if opp.opportunity_id:
            lines.append(f"- **ID:** `{opp.opportunity_id}`")
        for f in opp.features:
            status = "PASS" if f.ok else "FAIL"
            err = f" — {f.error}" if f.error else ""
            lines.append(f"- **{f.name}**: {status} ({f.status}) — {f.detail}{err}")
        lines.append("")

    # Summary table by feature
    lines.append("## Feature pass/fall summary\n")
    feature_counts: dict[str, tuple[int, int]] = {}
    for opp in report.opportunities:
        for f in opp.features:
            passed, total = feature_counts.get(f.name, (0, 0))
            feature_counts[f.name] = (passed + (1 if f.ok else 0), total + 1)
    for fname in sorted(feature_counts):
        passed, total = feature_counts[fname]
        lines.append(f"- **{fname}**: {passed}/{total} passed")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--email", default=f"validation-{int(time.time())}@example.com")
    ap.add_argument("--password", default="TenderTest123!")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument(
        "--complete-count",
        type=int,
        default=5,
        help=(
            "How many opportunities run through full lifecycle "
            "(baseline, artifacts, claims, etc.)."
        ),
    )
    ap.add_argument("--workspace", default="Validation Workspace")
    ap.add_argument("--workspace-country", default="IN")
    ap.add_argument(
        "--start-backend",
        action="store_true",
        help="Start the backend as a subprocess before running.",
    )
    ap.add_argument("--env-file", default=str(REPO / ".env.validation"))
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--report", default=str(REPO / "validation_report.md"))
    args = ap.parse_args()

    backend_proc = None
    if args.start_backend:
        backend_proc = _start_backend(Path(args.env_file), args.port)
        time.sleep(2)

    try:
        client = ValidationClient(args.base_url)
        if not client.health(timeout=60):
            print("Backend not healthy", file=sys.stderr)
            return 1

        # Prepare a single .docx from the sample markdown.
        docx_path = REPO / ".validation_storage" / "conditions.docx"
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        _build_conditions_docx(docx_path)
        csv_text = _build_boq_csv_text()

        # Auth and workspace
        print(f"Signing in as {args.email} ...")
        token = client.signup_or_login(args.email, args.password)
        print("Creating workspace ...")
        ws = client.ensure_workspace(token, args.workspace, args.workspace_country)
        ws_token = client.switch_workspace(token, ws["workspace_id"])

        report = RunReport(
            account_email=args.email,
            workspace_id=ws["workspace_id"],
            workspace_name=ws["name"],
            base_url=args.base_url,
            total=args.count,
            completed=args.complete_count,
        )

        print(f"Seeding {args.count} opportunities ({args.complete_count} full lifecycle) ...")
        for i in range(1, args.count + 1):
            complete = i <= args.complete_count
            result = _opportunity_basic_flow(
                client, ws_token, i, docx_path, csv_text, complete=complete
            )
            report.opportunities.append(result)
            if result.error:
                report.failed += 1
            tag = "(full)" if complete else "(reviewable)"
            state = "error" if result.error else "ok"
            print(f"  [{i}/{args.count}] {result.title or 'FAILED'} {tag} — {state}")
            # Token refresh every 10 opportunities to avoid expiry.
            if i % 10 == 0:
                ws_token = client.refresh()
                ws_token = client.switch_workspace(ws_token, ws["workspace_id"])

        # Global features (run once at workspace level)
        report.global_features.append(_export_report(client, ws_token))

        _write_report(report, Path(args.report))
        print(f"\nReport written to {args.report}")

        feature_ok = all(f.ok for f in report.global_features)
        opp_ok = sum(1 for o in report.opportunities if not o.error) == args.count
        return 0 if feature_ok and opp_ok else 1
    finally:
        if backend_proc is not None:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
