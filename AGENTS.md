# Aura Coffee

Web platform for a local coffee shop — online ordering with pickup and own-courier delivery. Production system for a real coffee shop. Single location, single menu, no multitenancy.

**Authoritative design doc:** `docs/PRODUCT_DESIGN_DOCUMENT.md`
**GRACE artifacts:** `docs/{requirements,technology,development-plan,verification-plan,knowledge-graph,operational-packets}.xml`

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync) + Alembic, Celery + Redis, PyJWT
- **Frontend:** React 19 + TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router
- **API client:** Auto-generated from FastAPI OpenAPI spec
- **Data:** PostgreSQL 16, Redis 7
- **Infra:** Docker + Docker Compose, Nginx
- **Testing:** pytest + httpx (backend), Vitest (frontend); GRACE LDD log assertions via `shared.grace.testing.GraceLogCapture`

## Module Map

| Directory | Module Tag | GRACE ID | Purpose |
|-----------|-----------|----------|---------|
| `services/core-api/` | `[core-api]` | M-CORE-API | FastAPI HTTP server — business logic, CRUD, auth, all state mutations |
| `services/payment-worker/` | `[payment-worker]` | M-PAYMENT-WORKER | Celery worker — YuKassa payments, webhooks, refunds |
| `services/sms-worker/` | `[sms-worker]` | M-SMS-WORKER | Celery worker — SMS.ru OTP codes, order notifications |
| `web/customer/` | `[web-customer]` | M-WEB-CUSTOMER | React SPA — customer-facing: menu, cart, checkout, profile |
| `web/admin/` | `[web-admin]` | M-WEB-ADMIN | React SPA — staff panel: admin, barista, courier views |
| `packages/shared/` | `[shared]` | M-SHARED | Shared Python package — domain enums, GRACE LDD logger, validation |
| `database/` | `[database]` | M-DATABASE | Alembic migrations, seeds, schema |

## Cross-Cutting Constraints

These Inviolable Rules apply to ALL modules. See PDD §2 for full definitions.

- **INV-002 — Auth for mutations:** All state-mutating operations MUST require server-side authentication and role-based authorization. Client-side auth checks are NOT sufficient.
- **INV-004 — Atomic financials:** Points redemption, promo application, and payment creation MUST be wrapped in a single DB transaction. Partial state (points deducted, payment failed) is FORBIDDEN.
- **INV-013 — PII isolation:** Personal data (phone, name, addresses) MUST be stored separately from order data. Tables reference users by opaque UUID. Account deletion MUST anonymize PII while preserving order history.
- **INV-014 — Immutable order items:** UPDATE and DELETE on `order_items` are FORBIDDEN. Order items are snapshots of prices/names at time of order.
- **INV-015 — Secrets out of code:** All API keys, secrets, and connection strings MUST be in environment variables. Never in source code, git history, or config files.
- **INV-016 — Explicit state transitions only:** State machines in PDD §6 are exhaustive. Any transition NOT listed is FORBIDDEN. Do not invent, add, or imply transitions.

## State Machines

All state machines are defined in PDD §6. Reference them by section:

- §6.1 — Order Lifecycle (CREATED → PAID → PREPARING → READY → IN_DELIVERY → COMPLETED / CANCELLED)
- §6.2 — Payment Lifecycle (PENDING → AWAITING_CONFIRMATION → SUCCEEDED → REFUND_PENDING → REFUNDED)
- §6.3 — Delivery Assignment (AWAITING_COURIER → COURIER_ASSIGNED → PICKED_UP → DELIVERED)
- §6.4 — SMS OTP (CREATED → SENT → VERIFIED / EXPIRED / FAILED)
- §6.5 — User Account (PENDING_VERIFICATION → ACTIVE → BLOCKED → DELETED)
- §6.6 — Promocode (DRAFT → ACTIVE → PAUSED → EXPIRED / EXHAUSTED)

## Development Methodology: GRACE

This project uses **GRACE** (Graph-RAG Anchored Code Engineering). The full reference is the `grace:grace-explainer` skill plus the artifacts under `docs/`.

### Substrate (in-source)

Every public Python `def`/`class` and every public TypeScript export carries a paired contract. Mirror `packages/shared/src/shared/grace/logging.py`:

```python
# START_CONTRACT: function_name
#   PURPOSE: One sentence.
#   INPUTS:  param: Type — description
#   OUTPUTS: ReturnType — description
#   SIDE_EFFECTS: external state changes or "none"
#   LINKS:   PDD §x, INV-y, related modules
# END_CONTRACT: function_name
def function_name(...) -> ...:
    ...
```

Files also carry a top-level `# START_MODULE_CONTRACT` block (PURPOSE / SCOPE / DEPENDS / LINKS / ROLE / MAP_MODE) plus a `# START_MODULE_MAP` listing public exports. TypeScript files use `//` line comments with the same fields, placed AFTER the `import` block.

Declarative files (Pydantic schemas, SQLAlchemy ORM models) use `MODULE_CONTRACT` and `MODULE_MAP` only — the class declaration itself is the contract. Per-class function contracts on those files are noise.

See `docs/development-plan.xml` for the per-module contracts; the live knowledge graph is at `docs/knowledge-graph.xml`.

### Log-Driven Development (LDD)

State-machine transitions and atomic-transaction boundaries emit canonical log markers:

```
[CoreApi][orders.create][BLOCK_TX_BEGIN] user_id=...
[CoreApi][orders.create][BLOCK_STATE_TRANSITION] BELIEF: CREATED ACTUAL: CREATED STATUS: MATCH order_id=...
[CoreApi][orders.create][BLOCK_TX_COMMIT] order_id=...
```

Use `shared.grace.logging.get_grace_logger("ModuleLabel")` and call `.block(fn, blk, msg, **fields)` or `.belief(fn, blk, belief, actual, **fields)`. The required-log-markers per module live in `docs/verification-plan.xml`.

**INV-013 redaction is mandatory:** never log raw phone, OTP code, JWT, password, or full PAN. Only opaque IDs (uuid, otp_id, payment_id, etc.).

### Verification

Tests opt into LDD assertions with the `grace_logs` pytest fixture (defined in `packages/shared/tests/conftest.py` and re-exposed in `services/core-api/tests/conftest.py`):

```python
# GRACE-LDD: this test asserts on log trajectory
def test_x(grace_logs):
    ...  # call code under test
    grace_logs.assert_trajectory(
        ("orders.create", "BLOCK_TX_BEGIN"),
        ("orders.create", "BLOCK_STATE_TRANSITION"),
        ("orders.create", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
```

Existing pytest assertions are preserved — LDD is additive, not a replacement.

### Workflow skills (from the `grace` plugin)

| Skill | When |
|-------|------|
| `grace:grace-plan` | Designing a new module / phase / data flow before code |
| `grace:grace-execute` | Sequential implementation with controller-managed packets |
| `grace:grace-multiagent-execute` | Parallel implementation waves (use carefully) |
| `grace:grace-verification` | Adding tests / log markers / scenarios |
| `grace:grace-refactor` | Renaming / moving / splitting modules — keeps graph + contracts in sync |
| `grace:grace-fix` | Debugging via graph navigation |
| `grace:grace-refresh` | Sync GRACE artifacts with code after changes |
| `grace:grace-status` | Health check + suggested next action |
| `grace:grace-ask` | Architecture / implementation Q&A grounded in project artifacts |
| `grace:grace-reviewer` | Pre-merge or phase-boundary integrity review |

### Worktree dev workflow (utilities retained)

The orchestrate.sh + merge.sh + phase-plan.yaml batching flow has been retired (archived under `docs/.archive/` and `scripts/.archived/`). Worktree port collision avoidance and the canonical nginx entry point are still in use:

```bash
./scripts/setup-worktree-env.sh      # writes .env with collision-free port offsets
./scripts/up.sh                      # brings the full stack up, prints real host URLs
docker compose exec core-api pytest services/core-api/tests/ -v
```

**Canonical local entry point:** `http://localhost:${NGINX_PORT}/` (default 8240). **Ignore Vite log URLs** — they show container-internal ports, not host ports. Use the URLs `up.sh` prints.

### Migration history

GRACE was adopted via a 7-checkpoint migration. See `MIGRATION_LOG.md` for the commit-by-commit trail. Pre-GRACE artifacts are preserved (audit trail) under:

- `openspec/` — the original 97 archived spec changes + 77 capability specs
- `docs/.archive/phase-plans/` — 10 archived `phase*-plan.yaml` files
- `docs/.archive/manual-tests/` — 5 archived `phase*_manual_test_scenarios.md`
- `docs/.archive/legacy-claude/` — old `opsx/*.md` slash commands and `openspec-*` skills
- `scripts/.archived/` — `orchestrate.sh`, `merge.sh`, `phase-plan.example.yaml`

## Environment Workarounds

### Broken SSL in `/usr/local/bin/python3`

`/usr/local/bin/python3` (3.12.2) was compiled without SSL support — the `_ssl` C extension is missing entirely. Any code that imports `ssl` (pytest via anyio, redis, httpx, pip/uv network requests) crashes with `ModuleNotFoundError: No module named '_ssl'`.

**Working Python:** `/usr/bin/python3` (3.12.3) has full SSL support.

When creating venvs on the host (outside Docker), always specify the working interpreter explicitly:

```bash
uv venv --python /usr/bin/python3
# or
python3 -m venv .venv   # only if /usr/bin/python3 is first in PATH
```

If a venv already exists and tests fail with `_ssl` errors, delete and recreate it:

```bash
rm -rf .venv
uv venv --python /usr/bin/python3
uv pip install -e ".[dev]"
```

**Note:** This does NOT affect Docker containers — they use their own Python. Only matters for host-side test runs and scripts.

## General Rules

- Prices are stored as integers in kopecks (1₽ = 100). Display conversion is frontend responsibility.
- All timestamps are UTC (`TIMESTAMPTZ`). Timezone conversion is frontend responsibility.
- Bilingual: all user-facing text has RU + EN variants. DB fields: `name_ru`, `name_en`.
- Domain language is strict — use terms from PDD §3. Inconsistent naming is a bug.
- New code is GRACE-substrate from the start: contracts before functions, LDD markers at state transitions, paired START/END markup.
