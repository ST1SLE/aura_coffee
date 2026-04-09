## Context

The repo contains only `docs/` and `openspec/`. The PDD (§4) defines 7 logical modules with clear boundaries. The tech stack has been decided: Python backend (FastAPI + Celery), React frontend (TypeScript + Vite), PostgreSQL + Redis. The next step before any application code is establishing the directory structure and AGENTS.md hierarchy for parallel development.

**Affected modules:** [core-api], [payment-worker], [sms-worker], [web-customer], [web-admin], [shared], [database]

## Goals / Non-Goals

**Goals:**
- Establish directory structure that maps 1:1 to openspec module tags
- Create AGENTS.md files that enable parallel agent development with clear scope isolation
- Ensure every module directory exists and is tracked by git

**Non-Goals:**
- No package configs, Dockerfiles, or build tooling (deferred to project-init change)
- No application source code
- No CI/CD configuration

## Decisions

### Decision 1: Top-level directory organization

```
aura_coffee/
├── services/          # Backend microservices (Python)
│   ├── core-api/
│   ├── payment-worker/
│   └── sms-worker/
├── web/               # Frontend applications (React + TypeScript)
│   ├── customer/
│   └── admin/
├── packages/          # Shared internal packages
│   └── shared/
├── database/          # Migrations and seeds (Alembic)
├── deploy/            # Docker Compose, Nginx configs
├── scripts/           # Dev utilities
├── docs/              # PDD, ADRs (existing)
└── openspec/          # Spec-driven workflow (existing)
```

**Rationale:** `services/` groups all backend processes. `web/` groups all frontends. `packages/` holds shared code consumed by multiple services. This follows the monorepo convention used by projects like Turborepo and Nx, adapted for Python + Node hybrid repos.

**Alternative considered:** Flat top-level (core-api/, payment-worker/, web-customer/ all at root). Rejected because it clutters the root and loses the visual grouping of related modules.

### Decision 2: AGENTS.md hierarchy (8 files)

```
AGENTS.md                              # Root: project overview, cross-module rules, INV constraints
├── services/core-api/AGENTS.md        # Core API scope: §4.1, §6, §7
├── services/payment-worker/AGENTS.md  # Payment scope: §4.2, §6.2, §8.1
├── services/sms-worker/AGENTS.md      # SMS scope: §4.3, §6.4, §8.2
├── web/customer/AGENTS.md             # Customer frontend: §4.4
├── web/admin/AGENTS.md                # Admin panel: §4.5, INV-010
├── packages/shared/AGENTS.md          # Shared package: domain models, enums
└── database/AGENTS.md                 # DB scope: §5, migrations, INV-013, INV-014
```

**Rationale:** Each AGENTS.md scopes an agent to its module's PDD sections, Inviolable Rules, and tech stack. An agent working in `services/payment-worker/` picks up both root AGENTS.md (global constraints) and its local AGENTS.md (YuKassa-specific rules). This prevents agents from making changes outside their boundary.

**Alternative considered:** Single root AGENTS.md with all instructions. Rejected because it would be too large and agents working on one module would carry irrelevant context about all other modules.

### Decision 3: Root AGENTS.md content strategy

The root AGENTS.md SHALL contain:
- Project summary (single paragraph)
- Tech stack reference
- Module map (directory → purpose → openspec tag)
- Cross-cutting constraints (INV rules that apply globally: INV-002, INV-004, INV-013, INV-014, INV-015, INV-016)
- Pointer to PDD as authoritative source

The root AGENTS.md SHALL NOT duplicate PDD content. It SHALL reference sections by number.

### Decision 4: Module AGENTS.md content strategy

Each module AGENTS.md SHALL contain:
- Module purpose (1-2 sentences)
- Owned PDD sections
- Module-specific INV rules
- Tech stack for this module
- Key files and entry points (to be updated as code is added)
- What this module MUST NOT do (boundary enforcement)

### Decision 5: .gitkeep placement

Empty directories that MUST exist in git:
- `services/core-api/src/`, `services/core-api/tests/`
- `services/payment-worker/src/`, `services/payment-worker/tests/`
- `services/sms-worker/src/`, `services/sms-worker/tests/`
- `web/customer/src/`, `web/admin/src/`
- `packages/shared/src/`, `packages/shared/tests/`
- `database/migrations/`, `database/seeds/`
- `deploy/`, `scripts/`

**Rationale:** `.gitkeep` files signal intended structure to future developers and agents. They SHALL be removed when real files are added.

## Risks / Trade-offs

- **[Risk] AGENTS.md content becomes stale as code evolves** → Mitigation: each module's AGENTS.md includes a "Key files" section that MUST be updated when entry points change. The `openspec` task rules already require module tags, creating natural checkpoints.
- **[Risk] Shared package creates tight coupling** → Mitigation: `packages/shared/` AGENTS.md SHALL explicitly restrict its scope to domain enums, constants, and Pydantic models. No business logic, no DB sessions, no API-specific code.
- **[Trade-off] Many small directories vs fewer larger ones** → Accepted: the granularity matches openspec module tags exactly, enabling clean task assignment.
