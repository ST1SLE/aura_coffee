## Why

The monorepo has only `.gitkeep` placeholders in `web/customer/src/` and `web/admin/src/` — no runnable frontend code exists. Before any feature work (Phase 1+) can begin, both React SPAs need working project scaffolding: Vite builds, TypeScript config, Tailwind CSS + shadcn/ui, i18n setup, routing skeleton, and dev tooling. This is Phase 0 alongside `project-init-backend`.

## What Changes

- **[web-customer]** Scaffold `web/customer/` as a React 19 + TypeScript SPA: Vite config, Tailwind CSS + shadcn/ui, react-i18next with RU/EN skeleton, React Router with placeholder routes, API client stub (for future OpenAPI codegen)
- **[web-admin]** Scaffold `web/admin/` as a React 19 + TypeScript SPA: same base stack, role-aware routing skeleton (admin/barista/courier views), react-i18next with RU/EN skeleton
- **[shared-ui]** Evaluate shared UI config — Tailwind preset and/or shadcn/ui theme tokens shared between both SPAs (if warranted; may stay inline)
- **[dev]** Vitest setup for both SPAs, ESLint + Prettier config, dev scripts in `scripts/`
- **[infra]** Add Nginx config for serving both SPAs in Docker Compose; update `docker-compose.yml` with frontend dev containers (Vite dev server with HMR)

## Non-Goals

- No business logic, real pages, or API integration — this is scaffolding only
- No OpenAPI client generation — requires a running core-api with spec (depends on `project-init-backend`)
- No authentication flows or protected routes — Phase 1 scope
- No CI/CD pipeline — deferred until deployment is scoped
- No SSR or static pre-rendering — both apps are client-side SPAs (PDD §4.4, §4.5)

## MVP Phase

Phase 0: Project Initialization

## Capabilities

### New Capabilities
- `vite-react-scaffold`: Vite + React 19 + TypeScript project structure, build config, dev server for both SPAs
- `tailwind-shadcn-setup`: Tailwind CSS configuration, shadcn/ui component library init, shared design tokens
- `i18n-setup`: react-i18next configuration with RU/EN namespace files and language switcher component
- `frontend-routing`: React Router setup with placeholder routes for customer and admin apps
- `frontend-dev-env`: Vitest config, ESLint + Prettier, Nginx config, Docker Compose integration for frontend services

### Modified Capabilities
<!-- None — this is the first frontend change, no existing specs -->

## Impact

- **Code:** `web/customer/` and `web/admin/` gain real React applications replacing `.gitkeep` files
- **Dependencies:** React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router, Vitest, ESLint, Prettier
- **Infrastructure:** Docker Compose gains frontend dev containers and Nginx reverse proxy; both SPAs accessible on `localhost` during dev
- **APIs:** No backend API dependency — apps render placeholder UI only
