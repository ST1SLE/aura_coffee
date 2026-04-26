# Customer Frontend

React SPA for customers — menu browsing, drink customization, cart, checkout, payment, profile, order tracking.

**PDD sections:** §4.4 (boundaries)

## Tech Stack

- React 19 + TypeScript, Vite
- Tailwind CSS + shadcn/ui
- react-i18next (bilingual RU/EN)
- React Router
- Auto-generated API client from FastAPI OpenAPI spec

## Scope

This module is responsible for:
- Menu display with categories, sizes, modifiers, stop-list indicators
- Drink/food customization UI (size selection, modifier toggles)
- Cart management (add/remove/update items, quantity)
- Checkout flow: delivery type selection (pickup/delivery), time slot selection (ASAP/specific), address input with Yandex.Maps autocomplete, promo code input, loyalty points redemption
- Payment redirect to YuKassa (or embedded widget)
- Order status page with live updates (polling 10s interval or WebSocket)
- Profile: display name, language preference, saved delivery addresses, order history, repeat order
- SMS OTP authentication flow

## Constraints

- **Mobile-first responsive:** Minimum viewport 320px. Breakpoints: mobile (320–767px), tablet (768–1023px), desktop (≥ 1024px).
- **Browser support:** Last 2 versions of Chrome, Safari, Firefox (mobile + desktop).
- **Bilingual RU/EN:** All UI text via react-i18next. Menu text (names, descriptions) comes from API in both languages. Language switch is client-side.
- **Prices always from server:** Frontend MUST NOT calculate prices locally. Subtotals, discounts, delivery fees, totals — all come from API responses. Display only.
- **Validation is UX, not security:** Client-side checks (stop-list, delivery radius, working hours) are hints. Server rejects invalid requests regardless. Never trust client state for business logic.
- **Order status freshness:** Status page MUST show updates within ≤ 10 seconds (polling or WebSocket, per §4.4).

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** Vitest + React Testing Library
- **Runner:** `npm test` in `web/customer/`
- **Test files:** colocated `<Component>.test.tsx` next to source
- **Methodology:** GRACE — verification via Vitest. Pure presentation components may still omit tests; logic-bearing exports (hooks, stores, API clients, complex pages) carry GRACE contracts and tests.
- **Mocks:** mock API calls, never mock React internals.
- Old RED/GREEN/IMPL/TEST distinctions retired; see root `AGENTS.md` and `MIGRATION_LOG.md`.

## This Module MUST NOT

- Calculate prices, discounts, or delivery fees
- Store auth tokens in localStorage (use httpOnly cookies or secure session)
- Contain API keys (Yandex.Maps key is proxied through core-api)
- Make direct calls to YuKassa, SMS.ru, or Yandex.Maps APIs
