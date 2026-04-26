# Admin Panel

React SPA for coffee shop staff — unified interface with role-filtered views for admin, barista, and courier.

**PDD sections:** §4.5 (boundaries), INV-010 (role isolation)

## Tech Stack

- React 19 + TypeScript, Vite
- Tailwind CSS + shadcn/ui
- react-i18next (bilingual RU/EN)
- React Router
- Auto-generated API client from FastAPI OpenAPI spec

## Scope

This module is responsible for:
- **Admin views:** Menu CRUD (categories, items, sizes, modifiers, photos), order management, user management (view, block, adjust loyalty points), promo code CRUD (§6.6), shop settings (working hours, delivery radius, fees, loyalty percent), analytics dashboard
- **Barista views:** Incoming order feed (real-time), order status transitions (accept → preparing → ready → handed out), stop-list toggle (items + modifiers)
- **Courier views:** Available delivery orders list, "take order" action, status transitions (picked up → delivered)

## Constraints

- **Role isolation (INV-010):**
  - Barista MUST NOT see menu management (except stop-list), user management, promo codes, or settings
  - Courier MUST NOT see anything except delivery order list and status controls
  - Role filtering MUST happen both on client (hide UI) AND server (API rejects unauthorized requests)
- **Real-time order feed:** New orders (status = `PAID`) MUST appear in barista feed within ≤ 5 seconds. Same for courier delivery feed. Implementation: polling (5s interval) or WebSocket.
- **Staff authentication:** Separate from customer auth. Login/password for `staff_accounts`, NOT SMS OTP.
- **Bilingual RU/EN:** Same i18n approach as customer frontend.

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** Vitest + React Testing Library
- **Runner:** `npm test` in `web/admin/`
- **Test files:** colocated `<Component>.test.tsx` next to source
- **Methodology:** GRACE — verification via Vitest. Pure presentation components may still omit tests; logic-bearing exports (hooks, stores, API clients, role-gated pages, state-transition triggers) carry GRACE contracts and tests. Role-gated routes/components must cite INV-002 (server enforces; client gate is UX redirect only).
- **Mocks:** mock API calls, never mock React internals.
- Old RED/GREEN/IMPL/TEST distinctions retired; see root `AGENTS.md` and `MIGRATION_LOG.md`.

## This Module MUST NOT

- Allow barista to edit menu items, manage users, or create promo codes
- Allow courier to access any data beyond delivery orders
- Rely solely on client-side role checks for security (server enforces INV-010)
- Expose customer PII (phone numbers, addresses) to courier role
