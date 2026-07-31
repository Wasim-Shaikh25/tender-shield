# 02 — `marketdata`: Employer Behaviour Graph (TS-195 → TS-200)

**Moat class 1** — proprietary data an LLM has never seen. Built entirely from public sources; needs
no customers. **Spec:** `specs/modules/marketdata.md`. **Sprint 3** in `tasks/phase16_tracker.md`.

**Depends on:** TS-224 (`app/evalcorpus/`, done — reuse it, do not re-implement harvesting).

> **The single most important design constraint in this module:** `md_*` tables are **reference
> data, NOT workspace-scoped.** They must contain **zero customer data**. Everything else in the
> backend uses `WorkspaceScopedMixin`; these tables deliberately do not. That inversion is the
> thing to get right and to pin with a test.

---

## TS-195 — Module scaffold

**Files to create**

```
backend/app/modules/marketdata/
├── __init__.py
├── module.py        # ModuleSpec — name MUST be "marketdata" (== dir == /api/marketdata)
├── models.py        # md_* tables (NO WorkspaceScopedMixin)
├── router.py
├── service.py
├── resolve.py       # TS-198 employer identity resolution (pure, deterministic)
├── aggregates.py    # TS-199 aggregate math (pure, deterministic, no LLM)
└── adapters.py      # TS-197 P0 source adapters (thin — reuse evalcorpus contracts)
backend/tests/test_marketdata.py
```

```python
# module.py
"""`marketdata` module registration (TS-195, specs/modules/marketdata.md).

Reference-data module: md_* tables are shared across all tenants and contain
no customer data (spec §Data owned). Everything it publishes degrades to
absence — risk findings render exactly as they do today when it is disabled."""

from app.core.module import AppContext, ModuleSpec
from app.modules.marketdata.router import router
from app.modules.marketdata.service import MarketDataService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    factory = lambda session: MarketDataService(session)          # noqa: E731
    reg.provide("marketdata.employer_profile", factory)
    reg.provide("marketdata.comparable_awards", factory)
    reg.provide("marketdata.price_benchmark", factory)

    # Opportunistically warm the profile cache — never block opportunity creation.
    def _on_opportunity_created(event: str, payload: dict) -> None:
        ...   # best-effort; exceptions are swallowed by the bus, but log intent

    ctx.events.subscribe("opportunity.created", _on_opportunity_created)


module = ModuleSpec(
    name="marketdata",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "rulepacks"),
    setup=setup,
)
```

**Acceptance gate (from the tracker):** *Boots with module disabled; no hard deps.*

```python
def test_app_boots_without_marketdata(monkeypatch):
    monkeypatch.setenv("TS_ENABLED_MODULES", "auth,ingestion,risk,findings,review")
    app = create_app(Settings())
    assert "marketdata" not in {s.name for s in app.state.load_report.loaded}
    # and a risk finding still renders with no employer context block
```

---

## TS-196 — Corpus schema + migrations (non-tenant)

**Tables** (`models.py`) — note `Base` + `TimestampMixin` only, **no `WorkspaceScopedMixin`**:

```python
from app.core.db import Base, TimestampMixin

class MdEmployer(Base, TimestampMixin):
    __tablename__ = "md_employers"                # plain __tablename__: no mixin to register it
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    family: Mapped[str] = mapped_column(String, nullable=False, index=True)   # CPWD, NHAI, mh_pwd
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resolution_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    raw_buyer_name: Mapped[str] = mapped_column(String, nullable=False)

class MdTender(Base, TimestampMixin):
    __tablename__ = "md_tenders"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ocid: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    employer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    classification: Mapped[str | None] = mapped_column(String, nullable=True)
    value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)   # NULL ≠ 0
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bid_opening_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # provenance (acceptance A9)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    adapter_version: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class MdAward(Base, TimestampMixin):
    __tablename__ = "md_awards"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ocid: Mapped[str] = mapped_column(String, nullable=False, index=True)
    winner_name: Mapped[str | None] = mapped_column(String, nullable=True)
    award_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    bidder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class MdProfile(Base, TimestampMixin):
    """Materialized aggregates. `sample_size` travels WITH the numbers, always."""
    __tablename__ = "md_profiles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employer_family: Mapped[str] = mapped_column(String, nullable=False, index=True)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    aggregates: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class MdHarvestRun(Base, TimestampMixin):
    __tablename__ = "md_harvest_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    adapter_version: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenders_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenders_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
```

**Money rule:** `app/evalcorpus/models.py` already implements the OCDS major→minor conversion with a
per-currency exponent table (0 for JPY/KRW, 3 for KWD/BHD/OMR, 2 default). **Import and reuse it** —
do not write a second converter. `None` for a missing amount, never `0`.

**The test that makes this task real** (tracker gate: *No tenant data in `md_*`, test-asserted*):

```python
def test_md_tables_are_not_workspace_scoped():
    from app.core.db import WORKSPACE_SCOPED_TABLES
    import app.modules.marketdata.models  # noqa: F401  (registers tables)
    md = {"md_employers", "md_tenders", "md_awards", "md_profiles", "md_harvest_runs"}
    assert md & WORKSPACE_SCOPED_TABLES == set(), (
        "md_* are shared reference data and must not carry workspace_id"
    )

def test_md_models_have_no_workspace_column():
    for model in (MdEmployer, MdTender, MdAward, MdProfile, MdHarvestRun):
        assert "workspace_id" not in model.__table__.columns
        assert "user_id" not in model.__table__.columns
```

Because these tables are outside RLS, **the router is the only isolation boundary** — every route
still requires an authenticated principal, it just doesn't filter rows by workspace.

---

## TS-197 — P0 source adapters (CPPP + one state NIC) — **P0**

Implement against the **existing** contract in `app/evalcorpus/adapters.py`
(`SourceAdapter` Protocol + `AdapterInfo`). One corpus, two consumers — the eval harness and this
module. Do not fork it.

```python
class CpppAdapter:
    """Central Public Procurement Portal (India).

    LEGALITY REVIEW (required by AdapterInfo — an adapter without one does not ship):
      - Terms of use reviewed: <date>, <url>
      - robots.txt:            <what it permits>
      - Official API:          none published as of <date>
      - Published rate limit:  none stated → self-imposed 1 req/sec, single connection
      - Access:                public archive search; NEVER behind a bidder login
    """
    def __init__(self, *, base_url: str, delay_seconds: float = 1.0) -> None:
        self.info = AdapterInfo(
            name="cppp", version="1.0", country="IN",
            legality="<paste the review above — it travels with the code>",
            requires_network=True, min_delay_seconds=1.0, max_concurrency=1,
        )
    def fetch_index(self, *, limit=None) -> Iterator[CorpusTender]: ...
    def fetch_documents(self, tender) -> Iterator[tuple[CorpusDocument, bytes]]: ...
    def fetch_awards(self, *, limit=None) -> Iterator[CorpusAward]: ...
```

**Known blocker, already documented** in `specs/eval-at-scale.md` §2.3:

> ⚠️ CPPP returned HTTP 403 to a datacenter IP during research. Harvesting will likely need an
> allowed egress path. **Resolve this legitimately** — an official data request or a compliant
> egress — never by evading a block.

Practical consequence for the agent: **build and test the adapter against recorded fixtures**
(`requires_network=False` fixture mode), and keep the live path behind an explicit flag. Do not add
retry-with-rotating-user-agent logic; that is block evasion and is out of scope by policy.

`state_nic` should be **parameterised per state** (one class, a state code argument), because NIC
eProcurement instances share a template.

**Acceptance:** legality review present in `AdapterInfo.legality` and the docstring; rate limiting
observed (assert the sleep/delay is applied between requests); offline fixture test passes with no
network.

---

## TS-198 — Employer identity resolution

Deterministic normalization pipeline. **Never LLM.** Real input looks like
`"E.E., PWD Div-II, Pune"`, `"Executive Engineer, P.W.D. Division No. 2, Pune"`.

```python
# resolve.py
@dataclass(frozen=True)
class Resolution:
    family: str | None
    division: str | None
    region: str | None
    confidence: float          # 0.0 – 1.0
    resolved: bool
    raw: str

HONORIFICS = ("shri", "smt", "the", "office of the")
ABBREVIATIONS = {           # loaded from rulepack data, not hardcoded long-term
    "e.e.": "executive engineer",
    "s.e.": "superintending engineer",
    "pwd":  "public works department",
    "div":  "division",
}

def normalize(raw: str) -> str:
    s = raw.casefold().strip()
    s = re.sub(r"[.,;]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    for h in HONORIFICS:
        if s.startswith(h):
            s = s[len(h):].strip()
    return " ".join(ABBREVIATIONS.get(tok, tok) for tok in s.split())

def resolve(raw: str, aliases: Mapping[str, str], *, threshold: float = 0.85) -> Resolution:
    """Exact alias hit → confidence 1.0. Otherwise deterministic similarity against
    the curated alias table. Below `threshold` the buyer stays UNRESOLVED —
    never guessed into a family (spec §Employer resolution)."""
    norm = normalize(raw)
    if norm in aliases:
        return Resolution(family=aliases[norm], ..., confidence=1.0, resolved=True, raw=raw)
    best, score = _closest(norm, aliases)     # difflib.SequenceMatcher — deterministic
    if score < threshold:
        return Resolution(None, None, None, confidence=score, resolved=False, raw=raw)
    return Resolution(family=aliases[best], ..., confidence=score, resolved=True, raw=raw)
```

Alias table lives in **rulepack data** (`rulepacks/in-works/employers/*.yaml`), versioned and
`source:`-attributed like every other pack file (`CLAUDE.md` §5). Consume it via
`reg.get("rulepacks.loader")` and degrade to a small built-in default when `rulepacks` is disabled.

**Acceptance:** confidence published on every resolution; an unknown buyer stays `resolved=False`
with its raw name intact; identical input → identical output (determinism test).

---

## TS-199 — Aggregates + suppression

Pure functions over `md_tenders` / `md_awards`. **No LLM anywhere in this path.**

```python
# aggregates.py
MIN_SAMPLE_SIZE = 12        # assumption: stated in spec §Suppression rule

class InsufficientData(Exception):
    def __init__(self, n: int):
        super().__init__(f"insufficient_data: n={n} < {MIN_SAMPLE_SIZE}")
        self.n = n

def compute_profile(tenders: Sequence[MdTender], awards: Sequence[MdAward]) -> dict:
    n = len(awards)
    if n < MIN_SAMPLE_SIZE:
        raise InsufficientData(n)
    return {
        "bidder_count_p50": _pct([a.bidder_count for a in awards if a.bidder_count], 50),
        "bidder_count_p90": _pct([...], 90),
        "l1_to_estimate_pct": _distribution(_l1_ratios(tenders, awards)),
        "award_latency_days": _distribution(_latencies(tenders, awards)),
        "retender_rate": _retender_rate(tenders),
        "winner_concentration": _hhi([a.winner_name for a in awards if a.winner_name]),
        "sample_size": n,
    }

def _hhi(winners: Sequence[str]) -> float:
    """Herfindahl–Hirschman index over award counts. Deterministic; sorted inputs."""
    total = len(winners)
    counts = Counter(winners)
    return round(sum((c / total) ** 2 for c in sorted(counts.values())), 6)
```

Two things the spec is emphatic about and that are easy to get wrong:

1. **Suppression, not approximation.** Below n=12 the API returns `insufficient_data` **with the
   actual n**, not a hedged number. *"A weak statistic is worse than no statistic"* — Build Doc §12.1.
2. **Determinism.** Sort before aggregating, `round()` at fixed precision, never iterate a set.
   The acceptance test asserts byte-identical output across two runs on the same input.

```python
def test_aggregates_are_deterministic():
    a = compute_profile(tenders, awards)
    b = compute_profile(list(reversed(tenders)), list(reversed(awards)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

def test_suppression_below_min_sample():
    with pytest.raises(InsufficientData) as exc:
        compute_profile(tenders[:5], awards[:5])
    assert exc.value.n == 5          # the real n is disclosed, not hidden
```

---

## TS-200 — Employer context on findings

**Routes** (`router.py`) — all read-only, all authenticated:

```
GET /api/marketdata/employers/{family}/profile
GET /api/marketdata/opportunities/{id}/comparables
GET /api/marketdata/opportunities/{id}/benchmark
```

`comparables` must **return the filter it used** (acceptance A5) — the user has to be able to see
what "comparable" meant:

```python
return {
    "filter": {
        "employer_family": family,
        "division": division,           # None when not narrowed
        "classification": classification,
        "value_band_minor": [low, high],
        "lookback_months": 36,
    },
    "sample_size": n,
    "awards": [...],
}
```

**The degradation requirement is the whole point of the task.** Consumers annotate findings via the
registry and must render exactly as today when the capability is absent:

```python
# in whichever module renders findings for the review workbench
profile_factory = reg.get("marketdata.employer_profile")
context = None
if profile_factory is not None:
    try:
        context = profile_factory(session).for_family(family)
    except InsufficientData:
        context = None                       # suppressed, not faked
    except Exception:
        logger.warning("marketdata unavailable; rendering finding without employer context")
return {**finding_payload, "employer_context": context}   # None is a valid, expected value
```

**Acceptance:** disabling `marketdata` leaves every other feature working (architecture/degradation
test); `insufficient_data` renders as no context block rather than an error.

---

## Suggested commit sequence

```
feat(marketdata): TS-195 module scaffold + graceful-absence tests
feat(marketdata): TS-196 md_* reference tables + non-tenant assertions   [1 migration]
feat(marketdata): TS-197 CPPP + state NIC adapters with legality review
feat(marketdata): TS-198 deterministic employer resolution with confidence
feat(marketdata): TS-199 aggregates with n>=12 suppression
feat(marketdata): TS-200 employer context on findings + read routes
```
