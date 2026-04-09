## Context

**Affected modules:** [web-customer], [web-admin]

The monorepo has two empty frontend directories (`web/customer/`, `web/admin/`) with only `.gitkeep` placeholders. Both SPAs share the same tech stack (React 19 + TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router) per PDD §4.4 and §4.5. The backend scaffolding is handled separately in `project-init-backend`.

Currently no `package.json`, no build config, no component library, no routing — nothing runnable. This design covers how to set up both apps from zero.

## Goals / Non-Goals

**Goals:**
- Both SPAs SHALL build and run independently via `npm run dev` with HMR
- Shared Tailwind config and shadcn/ui theme tokens between both apps
- i18n infrastructure (RU/EN) ready for feature work
- Routing skeleton with placeholder pages matching PDD user flows
- Vitest configured with at least one passing test per app
- Docker Compose integration: Vite dev servers + Nginx reverse proxy
- ESLint + Prettier enforcing consistent code style

**Non-Goals:**
- No business logic, API calls, or real UI components
- No OpenAPI client generation (requires running core-api)
- No authentication or protected routes
- No shared React component library — each app owns its components; sharing is limited to config (Tailwind preset, TypeScript paths)

## Decisions

### D1: Separate `package.json` per SPA (no monorepo package manager)

Each SPA (`web/customer/`, `web/admin/`) SHALL have its own `package.json` and `node_modules`. No npm/pnpm workspaces at the monorepo root.

**Rationale:** The two SPAs share a tech stack but not code. A workspace setup adds complexity (hoisting issues, phantom deps) without benefit — there are no shared React packages to deduplicate. Each app deploys independently.

**Alternatives considered:**
- pnpm workspaces: overhead for two leaf apps with no shared npm packages. Can revisit if a shared React component package emerges.

### D2: Tailwind preset in `web/shared-config/`

A shared Tailwind preset (`web/shared-config/tailwind-preset.js`) SHALL define brand colors, spacing scale, font stack, and border-radius tokens. Both SPAs extend this preset in their own `tailwind.config.ts`.

**Rationale:** Visual consistency between customer and admin apps without coupling them at build time. A preset is a plain JS object — no build step, no npm package.

**Alternatives considered:**
- Inline duplicate config: divergence risk as the project grows.
- Shared npm package: too heavy for a single config file.

### D3: shadcn/ui initialized independently per app

Each SPA SHALL run `npx shadcn@latest init` separately. The shared Tailwind preset ensures consistent CSS variables, so components look the same without code sharing.

**Rationale:** shadcn/ui is copy-paste by design — components live in the consuming project. Sharing components via a package contradicts the library's philosophy and adds build complexity.

### D4: react-i18next with namespace-per-feature structure

i18n SHALL use `react-i18next` with JSON namespace files:
```
web/customer/src/i18n/
  locales/
    ru/common.json
    en/common.json
  config.ts
```

Default language: `ru`. Fallback: `en`. Language detection: `localStorage` key.

**Rationale:** Namespace-per-feature scales well. Starting with a single `common` namespace; feature work adds new namespaces (e.g., `menu.json`, `checkout.json`).

### D5: React Router with flat route structure

Customer app routes (placeholders):
```
/           → Home / Menu
/cart       → Cart
/checkout   → Checkout
/orders     → Order history
/profile    → Profile
```

Admin app routes (placeholders):
```
/           → Dashboard
/orders     → Orders
/menu       → Menu management
/users      → User management
/promos     → Promocodes
/settings   → Shop settings
```

Each route SHALL render a minimal placeholder component (`<h1>Page Name</h1>`).

**Rationale:** Flat routes match PDD user flows. Nested routing can be added per-feature without restructuring.

### D6: Nginx reverse proxy configuration

Nginx SHALL route:
- `/` → `web-customer` Vite dev server (port 5173)
- `/admin` → `web-admin` Vite dev server (port 5174)
- `/api` → `core-api` (port 8000)

In production, Nginx SHALL serve static builds. For dev, it proxies to Vite HMR servers.

**Rationale:** Single entry point (`localhost:80`) mimics production topology. Avoids CORS complexity during development.

### D7: Vitest for unit testing

Both SPAs SHALL use Vitest with `@testing-library/react`. Initial test: verify the app renders without crashing.

**Rationale:** Vitest is the standard for Vite projects — zero-config, same transform pipeline, fast.

## Risks / Trade-offs

- **[Risk] Tailwind preset drift** → Both apps import the same preset file. Any change applies to both. Mitigation: preset changes SHALL be reviewed for impact on both apps.
- **[Risk] shadcn/ui version divergence** → Independent init means different component versions over time. Mitigation: acceptable for scaffolding; version alignment becomes relevant only when UI consistency matters across apps.
- **[Risk] No shared TypeScript types** → Domain types (Order, MenuItem, etc.) will be duplicated until OpenAPI client generation is in place. Mitigation: this is intentional — API client generation (Phase 1+) will be the single source of types.
- **[Risk] Nginx config complexity in dev** → Proxy to multiple Vite servers adds a moving part. Mitigation: Docker Compose healthchecks; developers can also run SPAs directly without Nginx.
