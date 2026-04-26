# Aura Coffee — Claude / Agent Onboarding

This is the production web platform for a single-location coffee shop. See `AGENTS.md` for the full project overview and `docs/PRODUCT_DESIGN_DOCUMENT.md` for the authoritative product spec.

## Methodology

The project uses **GRACE** (Graph-RAG Anchored Code Engineering). Six XML artifacts in `docs/` describe the substrate:

- `docs/requirements.xml` — index pointing back at the PDD (do NOT duplicate PDD content)
- `docs/technology.xml` — stack, tooling, observability, autonomy policy
- `docs/development-plan.xml` — modules, data flows, implementation order, execution policy
- `docs/verification-plan.xml` — required log markers, scenarios, phase gates
- `docs/knowledge-graph.xml` — module map + dependencies
- `docs/operational-packets.xml` — canonical packet/delta/failure templates

The `grace-*` skills (provided by the `grace` plugin) are the primary workflow surface. See root `AGENTS.md` Workflow section for the full table.

## Reading priority for an agent

1. `AGENTS.md` (root) — module map, INV constraints, methodology summary
2. `docs/PRODUCT_DESIGN_DOCUMENT.md` — authoritative product spec (~108k)
3. `docs/development-plan.xml` — what each module owns
4. `<module>/AGENTS.md` — module-local context for whichever module you're working in
5. `packages/shared/src/shared/grace/logging.py` — canonical contract format example

## Doing work

- Writing or modifying code? → Add a contract above each public function (see root `AGENTS.md` "Substrate" section). Emit LDD markers at state-machine transitions or atomic-transaction boundaries via `shared.grace.logging.get_grace_logger`.
- Adding a state-machine transition? → Update PDD §6 first. INV-016 forbids implicit transitions.
- Touching financial flows? → INV-004 (atomic transactions). Touching PII? → INV-013 (no phone/name/address in logs). Touching mutations? → INV-002 (server-side auth + RBAC).
- Tests can opt into LDD log assertions via the `grace_logs` pytest fixture; tag the file with a `# GRACE-LDD` header.

When in doubt, invoke `grace:grace-ask` for an answer grounded in the GRACE artifacts.

## Migration history

GRACE was adopted via a 7-checkpoint migration starting at commit `7534d83` (CP1 bootstrap) and ending at the CP7 docs commit. The full trail is in `MIGRATION_LOG.md`. Pre-GRACE artifacts (OpenSpec, phase-plan.yaml, opsx skills, manual tests, orchestrate.sh) are preserved as audit trail under `openspec/`, `docs/.archive/`, `scripts/.archived/`, and `docs/.archive/legacy-claude/`.

## Quickstart

```bash
cp .env.example .env
./scripts/setup-worktree-env.sh    # picks collision-free host ports
./scripts/up.sh                    # brings the full stack up
# Open http://localhost:${NGINX_PORT}/ — default 8240
docker compose exec core-api pytest services/core-api/tests/ -v
```

See root `AGENTS.md` for full environment notes (broken `/usr/local/bin/python3`, port collision avoidance, etc.).
