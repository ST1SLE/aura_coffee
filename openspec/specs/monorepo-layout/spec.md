## ADDED Requirements

### Requirement: Backend services directory structure
The repo SHALL contain a `services/` directory with three subdirectories: `core-api/`, `payment-worker/`, `sms-worker/`. Each service directory SHALL contain `src/` and `tests/` subdirectories. This maps to PDD §4.1–§4.3.

#### Scenario: All backend service directories exist
- **WHEN** a developer clones the repo
- **THEN** the paths `services/core-api/src/`, `services/core-api/tests/`, `services/payment-worker/src/`, `services/payment-worker/tests/`, `services/sms-worker/src/`, `services/sms-worker/tests/` SHALL all exist

### Requirement: Frontend applications directory structure
The repo SHALL contain a `web/` directory with two subdirectories: `customer/` and `admin/`. Each SHALL contain a `src/` subdirectory. This maps to PDD §4.4–§4.5.

#### Scenario: All frontend directories exist
- **WHEN** a developer clones the repo
- **THEN** the paths `web/customer/src/` and `web/admin/src/` SHALL both exist

### Requirement: Shared package directory structure
The repo SHALL contain `packages/shared/` with `src/` and `tests/` subdirectories. This package holds domain models, enums, constants, and validation shared across backend services.

#### Scenario: Shared package directory exists
- **WHEN** a developer clones the repo
- **THEN** the paths `packages/shared/src/` and `packages/shared/tests/` SHALL both exist

### Requirement: Database directory structure
The repo SHALL contain a `database/` directory with `migrations/` and `seeds/` subdirectories. This maps to PDD §5.5 (all schema changes via migrations).

#### Scenario: Database directories exist
- **WHEN** a developer clones the repo
- **THEN** the paths `database/migrations/` and `database/seeds/` SHALL both exist

### Requirement: Infrastructure and utility directories
The repo SHALL contain `deploy/` (Docker Compose, Nginx configs) and `scripts/` (dev utilities) directories at the root level.

#### Scenario: Deploy and scripts directories exist
- **WHEN** a developer clones the repo
- **THEN** the paths `deploy/` and `scripts/` SHALL both exist

### Requirement: Empty directories tracked via .gitkeep
All empty directories SHALL contain a `.gitkeep` file to ensure git tracks them. `.gitkeep` files SHALL be removed when real files are added to the directory.

#### Scenario: Empty directories are preserved in git
- **WHEN** a developer clones the repo and runs `find . -name .gitkeep`
- **THEN** every leaf directory in the structure SHALL contain a `.gitkeep` file

### Requirement: Directory-to-module-tag mapping
Each top-level module directory SHALL map to exactly one openspec module tag. The mapping SHALL be: `services/core-api/` → `[core-api]`, `services/payment-worker/` → `[payment-worker]`, `services/sms-worker/` → `[sms-worker]`, `web/customer/` → `[web-customer]`, `web/admin/` → `[web-admin]`, `packages/shared/` → `[shared]`, `database/` → `[database]`.

#### Scenario: Openspec task tags match directories
- **WHEN** an openspec task is tagged `[core-api]`
- **THEN** all file changes for that task SHALL be within `services/core-api/` (or `packages/shared/` if the task explicitly touches shared code)
