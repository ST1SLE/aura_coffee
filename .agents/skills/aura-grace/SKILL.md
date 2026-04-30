---
name: aura-grace
description: Use when working in Aura Coffee with GRACE methodology, including requests that mention GRACE, PDD, LDD, contracts, state machines, operational packets, knowledge graph, grace:grace-plan, grace:grace-execute, grace:grace-verification, grace:grace-refactor, grace:grace-refresh, grace:grace-fix, grace:grace-status, grace:grace-ask, or grace:grace-reviewer.
---

# Aura Coffee GRACE Workflow

Use this skill as the Codex-native replacement for the Claude `grace:*` plugin workflows in Aura Coffee.

## Required Context

Start with the smallest relevant set of files:

1. `AGENTS.md` for project-wide rules, module map, invariants, and environment notes.
2. `docs/PRODUCT_DESIGN_DOCUMENT.md` for product behavior, domain language, state machines, and invariants.
3. `docs/development-plan.xml` for module ownership and expected flows.
4. `docs/verification-plan.xml` for required scenarios and LDD markers.
5. `docs/knowledge-graph.xml` for cross-module dependencies.
6. The nearest module `AGENTS.md` for local constraints.
7. `packages/shared/src/shared/grace/logging.py` when implementing or reviewing contract/logging style.

Do not load every artifact by default. Read only the sections needed for the task.

## Core Rules

- PDD behavior is authoritative. If implementation and PDD disagree, stop and call out the conflict.
- INV rules in root `AGENTS.md` apply across the project.
- New public Python `def`/`class` and public TypeScript exports need GRACE contracts.
- State-machine transitions and atomic transaction boundaries need LDD markers when required by `docs/verification-plan.xml`.
- LDD assertions are a hard gate when touching state transitions, transaction boundaries, auth/role checks, OTP/SMS, payment webhooks, PII/secrets/logging paths, or code with required markers in `docs/verification-plan.xml`.
- Never log raw phone numbers, OTP codes, JWTs, passwords, full PAN, or other PII/secrets.
- Prices are stored as integer kopecks. Frontends display server-provided prices; they do not calculate business totals.
- State-machine changes require a PDD §6 update first. INV-016 forbids implicit transitions.

## LDD Verification Gate

Before marking an implementation or fix packet complete, decide whether LDD assertions are required.

LDD assertions are required if the packet touches any of:

- PDD §6 state-machine transitions or transition guards.
- Atomic transaction boundaries, payment/loyalty/promo/order creation, or rollback behavior.
- Auth, role checks, customer identity, OTP, SMS, payment webhooks, PII/secrets, or logging paths.
- Code that emits, changes, removes, or is expected to emit required markers from `docs/verification-plan.xml`.

When required:

1. Identify the required markers from `docs/verification-plan.xml`.
2. Add or update tests using the module's `grace_logs` fixture when available.
3. If the module does not expose `grace_logs`, use `shared.grace.testing.GraceLogCapture` directly or add a narrow local fixture.
4. Assert ordered trajectories with `assert_trajectory(...)` for state-machine and transaction paths.
5. Assert no mismatched beliefs: `grace_logs.beliefs(status="MISMATCH") == []`.
6. Assert INV-013 redaction in captured logs for auth/SMS/PII paths: no raw phone, OTP code, JWT, password, full PAN, API key, raw webhook body, or full address.

If LDD is not applicable, say why in the final report. The final report for every packet must list markers asserted, redaction checks asserted, verification commands run, and any required markers left untested with a reason.

## Workflow Selection

Map Claude-era workflow names to these Codex actions:

| User intent | Codex action |
| --- | --- |
| `grace:grace-plan`, design, phase planning | Produce a GRACE plan only. Do not edit files. |
| `grace:grace-execute`, implement packet/phase | Implement sequentially with contracts, LDD markers, and tests. |
| `grace:grace-verification`, add tests | Focus on tests, scenarios, and log marker assertions. |
| `grace:grace-refactor` | Refactor while keeping contracts, module maps, and references coherent. |
| `grace:grace-refresh` | Update GRACE artifacts after code changes. Do not invent product behavior. |
| `grace:grace-fix`, debug | Trace from symptom to artifact, code path, test, and fix. |
| `grace:grace-status` | Summarize current module health and next safest action. |
| `grace:grace-ask` | Answer architecture or implementation questions grounded in artifacts. |
| `grace:grace-reviewer`, review | Review for invariant, contract, LDD, test, and cross-module drift. |

## Planning Output

For planning tasks, return:

1. Scope and target module.
2. Relevant PDD/XML/module sections to read.
3. Required invariants.
4. Implementation steps.
5. Verification commands.
6. Risks and rollback path.

Do not write code in planning mode.

## Implementation Workflow

1. Inspect existing nearby patterns before editing.
2. Confirm the module boundary and dependency direction.
3. Add or update GRACE contracts before public functions/classes/exports.
4. Implement the smallest behavior change that satisfies the PDD and task.
5. Add required LDD markers for state transitions or transaction boundaries.
6. Add or update LDD assertions when the LDD Verification Gate applies.
7. Add or update non-LDD tests at the appropriate level.
8. Run the narrowest relevant verification command.
9. Report changed files, markers asserted, redaction assertions, verification status, and any untested required markers.

## Verification Guidance

Prefer these checks when relevant:

- Full stack smoke: `./scripts/up.sh`
- Core API tests: `docker compose exec core-api pytest services/core-api/tests/ -v`
- Shared package tests: `pytest packages/shared/tests/ -v`
- Payment worker tests: `pytest services/payment-worker/tests/ -v`
- SMS worker tests: `pytest services/sms-worker/tests/ -v`
- Admin frontend tests: `npm test` from `web/admin/`
- Customer frontend tests: `npm test` from `web/customer/`
- Frontend build: `npm run build` from the relevant frontend app.
- Python lint: `ruff check .`

Use host Python carefully. Root `AGENTS.md` documents that `/usr/local/bin/python3` lacks SSL; prefer `/usr/bin/python3` for host venvs.

For GRACE-sensitive changes, normal test pass/fail is not enough. Also report the specific LDD marker assertions that ran. If a touched module lacks LDD fixture wiring, either add a narrow fixture or use `GraceLogCapture` directly.

## Review Checklist

When reviewing Aura Coffee work, check:

- PDD consistency and exact domain language.
- INV-002 server-side auth for mutations.
- INV-004 atomic financial operations.
- INV-013 PII isolation and log redaction.
- INV-014 immutable order items.
- INV-015 no secrets in code/config/history.
- INV-016 explicit state transitions only.
- GRACE contracts and module maps remain paired and current.
- Required LDD markers are emitted and tested where applicable.
- Frontend role checks are UX only; backend enforces authorization.

Lead review output with findings ordered by severity. If no issues are found, say so directly and list unrun checks.

## Artifact Refresh Rules

Only refresh GRACE artifacts when code or behavior changed enough to make them stale.

- Update `docs/development-plan.xml` for module ownership, flow, or implementation-order changes.
- Update `docs/verification-plan.xml` for scenario or required-marker changes.
- Update `docs/knowledge-graph.xml` for dependency changes.
- Update `docs/PRODUCT_DESIGN_DOCUMENT.md` before adding or changing product behavior or state transitions.

Do not rewrite XML broadly. Make focused edits and preserve existing structure.
