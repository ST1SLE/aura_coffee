# GRACE Migration Log

Migrating `aura_coffee` from dev-workflow-kb (PDD/OpenSpec/2-phase-TDD/orchestrate) to GRACE (graph + in-source contracts + LDD).

**Started:** 2026-04-26
**Branch:** `dev`
**Plan:** 7 commits across 7 checkpoints. Light retrofit (public API only). English content. `openspec/` preserved untouched.
**Mode:** `--dangerously-skip-permissions` (autonomous). User offline.

## Live status

| CP | Status | Commit | Notes |
|----|--------|--------|-------|
| CP0 | completed | — | 8 worktrees pruned (no commit needed) |
| CP1 | completed | 7534d83 | GRACE bootstrap (docs/*.xml + LDD logger) |
| CP2 | completed | c9933aa | Mothball OpenSpec layer |
| CP3 | in_progress | — | Python contract retrofit (5 modules) |
| CP4 | pending | — | TS contract retrofit (2 modules) |
| CP5 | pending | — | LDD logging wire-up |
| CP6 | pending | — | LDD test fixtures |
| CP7 | pending | — | Docs finalization |

## Decisions log

(autonomous calls and deviations recorded here as they happen)

- **CP1 — AGENTS.md preserved at root.** `grace-init` template warns when `AGENTS.md` exists. Existing 9.5k AGENTS.md is full of dev-workflow-kb TDD content that needs context-aware rewriting (planned for CP7). Decision: keep existing AGENTS.md untouched at CP1, rewrite at CP7 once contracts are in place and the TDD section can be replaced cleanly.
- **CP1 — `requirements.xml` is INDEX, not duplicate.** PDD is 108k. `docs/requirements.xml` references PDD §X and INV-IDs rather than duplicating content (per user "do not duplicate" instruction in original plan).
- **CP1 — LDD logger placed at `packages/shared/src/shared/grace/`.** Import path: `from shared.grace.logging import GraceLogger, get_grace_logger`. Lightweight wrapper around stdlib logging — does NOT replace existing `logger = logging.getLogger(__name__)` calls. Smoke-tested: emits exact `[Module][fn][BLOCK]` and BELIEF/ACTUAL/STATUS=MATCH|MISMATCH formats prescribed by `docs/verification-plan.xml`.

---

## Detailed activity

### CP0 (preflight) — completed
- Pruned 8 stale "prunable" worktrees (`git worktree prune`); .worktrees/ dir cleaned.
- Plugin `osovv/grace-marketplace` confirmed loaded (14 grace-* skills available).
- Skipped explicit `grace-explainer` smoke — running `grace-init` is a stronger smoke.

### CP1 (GRACE bootstrap) — completed (commit 7534d83)
- Invoked `grace:grace-init`; populated all 6 docs/*.xml from templates with aura_coffee data.
- Created `packages/shared/src/shared/grace/{__init__,logging}.py` — LDD helper with `.block()` and `.belief()`. Smoke-tested import + emission via system Python with PYTHONPATH=packages/shared/src.
- AGENTS.md left untouched (decision logged above; revisit at CP7).

### CP2 (mothball OpenSpec process layer) — completed (commit c9933aa)
- Archived 4 opsx command files. Initial move into `.claude/commands/.archived-opsx/` was reverted because the harness auto-discovered the renamed directory as a new plugin namespace and exposed `.archived-opsx:opsx:apply` etc. as live skills. Final destination: `docs/.archive/legacy-claude/commands-opsx/` (outside the `.claude/` discovery path).
- Archived 4 openspec skills. Same discovery issue — final destination `docs/.archive/legacy-claude/skills-openspec/`.
- Archived 10 phase-plan YAMLs: `docs/phase*-plan*.yaml` → `docs/.archive/phase-plans/`.
- Archived 5 manual-test scenarios: `docs/phase*_manual_test_scenarios.md` → `docs/.archive/manual-tests/`.
- Archived 3 workflow scripts: `scripts/{orchestrate.sh,merge.sh,phase-plan.example.yaml}` → `scripts/.archived/`. Kept `setup-worktree-env.sh` and `up.sh` (still useful utilities; not workflow).
- **Skipped `.claude/settings.local.json` trim** — the harness's permission auto-learning kept appending entries to the file every time a bash command ran, racing with my Write. The 11 `Bash(openspec ...)` patterns are harmless allowlist noise (the openspec binary is not invoked anywhere now); cleaning them up would have cost several retries with no functional benefit. Decision: leave the allowlist as-is. User's CP7 docs pass can prune at leisure if desired.
- Left `openspec/` directory untouched (97 archived changes, 77 specs preserved as audit trail per user instruction "do not delete").

### CP3 (Python contract retrofit) — in progress
- 7 parallel subagents executed against non-overlapping write scopes; all reported success and produced ast-clean output.
- **113 Python files modified** across 5 modules: 113 MODULE_CONTRACT, 111 MODULE_MAP (2 files use MAP_MODE: NONE — env.py CONFIG and seeds/__init__.py marker), 261 function CONTRACT pairs. Comments only — no signatures, behavior, or imports changed.
- Per-module breakdown:
  - **M-SHARED** (19 files): module-level only on ORM models + enums + grace package init. ROLE: TYPES on declarative model files, ROLE: RUNTIME on grace/.
  - **M-CORE-API/routers** (19 files): module + 69 fn contracts on every route handler.
  - **M-CORE-API/services** (25 files): module + 151 fn contracts. Largest module by far.
  - **M-CORE-API/{schemas,deps,middleware,main,celery_app,database,rbac_matrix}** (27 files): module + 7 fn contracts (Pydantic schemas declarative-only).
  - **M-PAYMENT-WORKER** (9 files): module + 18 fn contracts on Celery tasks, webhook handler, YuKassa clients.
  - **M-SMS-WORKER** (9 files): module + 7 fn contracts on Celery tasks and SMS.ru clients.
  - **M-DATABASE** (5 files: env.py + 4 seed scripts): module + 4 fn contracts. The 8 `database/migrations/versions/*.py` files were skipped per brief (immutable historical snapshots).
- Smoke-tested: `import shared.enums`, `import shared.grace.logging` work cleanly.

**Concerns flagged for human review (NONE BLOCKING — surface as PDD §6 follow-ups when convenient):**
1. **Promocode lifecycle is computed, not stored.** No `PromocodeStatus` enum in `shared.enums`; promocode state derives from `is_active` + date window + `current_uses`. PDD §6.6 may want an explicit enum to match INV-016 exhaustiveness, but the current code is correct as-is.
2. **notification.py state matrix gap.** Subagent on M-CORE-API/services flagged that `notification.py` matrix omits `CREATED → PAID` and `CREATED → CANCELLED`. The zero-total checkout path in `services/checkout.create_order` sets `Order.PAID` directly without notification. Could be deliberate; verify against PDD §6.1 if a missing notification surfaces in QA.
3. **Payment.REFUND_FAILED state.** `webhook._handle_refund_canceled` writes `Payment.REFUND_FAILED`. PDD §6.2's visible chain is `REFUND_PENDING → REFUNDED`. May need to be added to §6.2 explicit transitions for INV-016 exhaustiveness.
