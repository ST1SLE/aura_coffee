## Why

The repo currently contains only `docs/` and `openspec/`. Before any application code can be written, the monorepo needs a directory structure that reflects the module boundaries defined in the PDD (§4) and supports parallel agent development via nested AGENTS.md files. Without this, there are no clear boundaries for where code goes, no agent-scoped instructions, and no foundation for the 6 MVP phases (§7.1).

## What Changes

- Create the full monorepo directory tree: `services/` (core-api, payment-worker, sms-worker), `web/` (customer, admin), `packages/shared/`, `database/`, `deploy/`, `scripts/`
- Create 8 AGENTS.md files (root + 7 module-level) defining scope, constraints, and PDD references for each boundary
- Add `.gitkeep` files to preserve empty directories in git
- No application code, no dependencies, no configs beyond structure

## Non-Goals

- **No application code or boilerplate.** This change creates directories and AGENTS.md files only. Package configs (`pyproject.toml`, `package.json`), Dockerfiles, and source code are separate changes per MVP phase.
- **No tech stack initialization.** Installing dependencies, configuring linters, setting up build tools — all deferred to a future `project-init` change.
- **No CI/CD pipeline.** GitHub Actions, deployment configs, and automation are out of scope.

## MVP Phase

This is **Phase 0 (pre-phase)** — structural foundation that all 6 MVP phases (§7.1) depend on.

## Capabilities

### New Capabilities

- `monorepo-layout`: Directory structure defining module boundaries, file organization conventions, and the relationship between services, frontends, shared packages, and infrastructure
- `agent-boundaries`: AGENTS.md hierarchy defining per-module agent scope, constraints, PDD references, and cross-module rules for parallel development

### Modified Capabilities

(none — no existing specs)

## Impact

- **All future changes** depend on this structure. Module tags in openspec tasks (`[core-api]`, `[web-customer]`, etc.) map directly to these directories.
- **Parallel development** becomes possible once AGENTS.md files define clear boundaries.
- **No breaking changes** — repo currently has no application code.
