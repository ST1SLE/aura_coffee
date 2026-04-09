## ADDED Requirements

### Requirement: Vitest configured in both SPAs
Both SPAs SHALL have Vitest installed and configured with `@testing-library/react` and `jsdom` environment. Running `npm test` SHALL execute all test files matching `**/*.test.{ts,tsx}`.

#### Scenario: Tests run successfully
- **WHEN** developer runs `npm test` in either SPA directory
- **THEN** Vitest executes all test files and reports results

#### Scenario: Smoke test passes
- **WHEN** the initial smoke test runs (App component renders without crashing)
- **THEN** the test passes

### Requirement: ESLint configured in both SPAs
Both SPAs SHALL have ESLint configured with `@eslint/js`, `typescript-eslint`, and `eslint-plugin-react-hooks`. Running `npm run lint` SHALL check all source files.

#### Scenario: Lint errors are reported
- **WHEN** a source file contains a lint violation
- **THEN** `npm run lint` reports the violation with file path and line number

### Requirement: Prettier configured in both SPAs
Both SPAs SHALL have Prettier configured with a shared `.prettierrc` config. Running `npm run format` SHALL format all source files. Running `npm run format:check` SHALL verify formatting without modifying files.

#### Scenario: Formatting is enforced
- **WHEN** a source file has inconsistent formatting
- **THEN** `npm run format:check` exits with a non-zero code

### Requirement: Nginx reverse proxy for development
The Docker Compose config SHALL include an Nginx service that routes:
- `/` → customer SPA (Vite dev server, port 5173)
- `/admin` → admin SPA (Vite dev server, port 5174)
- `/api` → core-api (port 8000)

#### Scenario: Customer app accessible via Nginx
- **WHEN** developer opens `http://localhost/` in a browser
- **THEN** the customer SPA is served via Nginx proxy

#### Scenario: Admin app accessible via Nginx
- **WHEN** developer opens `http://localhost/admin` in a browser
- **THEN** the admin SPA is served via Nginx proxy

### Requirement: Docker Compose frontend services
Docker Compose SHALL include services for both SPAs running Vite dev servers with volume mounts for HMR. The services SHALL depend on the Nginx service.

#### Scenario: Frontend starts with Docker Compose
- **WHEN** developer runs `docker compose up`
- **THEN** both Vite dev servers start and are accessible through Nginx

### Requirement: Dev scripts
The `scripts/` directory SHALL contain convenience scripts:
- `scripts/lint-frontend.sh` — runs ESLint on both SPAs
- `scripts/format-frontend.sh` — runs Prettier on both SPAs

#### Scenario: Lint script checks both apps
- **WHEN** developer runs `scripts/lint-frontend.sh`
- **THEN** ESLint runs on both `web/customer/` and `web/admin/` source files
