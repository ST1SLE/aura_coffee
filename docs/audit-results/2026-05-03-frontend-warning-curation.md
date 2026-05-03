# Aura Coffee Frontend Warning Curation

Date: 2026-05-03

Source: `docs/audit-results/2026-05-02-verification-audit.md` P2,
"Stale/flaky-test signal is not curated".

## Scope

This packet handles the current frontend warning baseline:

- Radix Dialog missing-description warnings in admin modal tests;
- admin BrowserRouter basename warnings in `App.test.tsx`;
- current customer/admin Vitest suites checked for React `act(...)` warning
  regressions;
- full-gate protection against new frontend Vitest stderr output.

## Changes

- Added screen-reader-only `DialogDescription` content for the admin promo,
  menu item, and user detail dialogs.
- Adjusted admin `App` smoke tests to render under `/admin`, matching the
  production `BrowserRouter basename="/admin"`.
- Added `test:stderr-clean` scripts to both frontend packages through
  `web/shared-config/check-vitest-clean-stderr.sh`.
- Updated `scripts/verify-full.sh` to run the stderr-clean frontend test
  scripts instead of plain `npm run test`.

## Verification

Commands run for this packet:

```bash
npm --prefix web/admin test -- \
  PromoFormDialog.test.tsx \
  MenuItemFormDialog.test.tsx \
  UserDetailDialog.test.tsx \
  App.test.tsx \
  Layout.test.tsx \
  --run
# 40 passed; no stderr warnings

npm --prefix web/admin test
# 307 passed; no stderr warnings

npm --prefix web/customer test
# 239 passed; no stderr warnings

npm --prefix web/admin run test:stderr-clean
# 307 passed; stderr-clean wrapper passed

npm --prefix web/customer run test:stderr-clean
# 239 passed; stderr-clean wrapper passed

npm --prefix web/admin run lint
npm --prefix web/admin run typecheck
npm --prefix web/customer run lint
npm --prefix web/customer run typecheck
# all passed
```

## GRACE/LDD

LDD assertions are not required for this packet. It changes frontend
accessibility metadata, frontend test setup, package scripts, and the
verification gate only. No backend auth behavior, state transitions,
transaction boundaries, PII/secrets/logging path, or required LDD marker path
changed.

Markers asserted: none.

Redaction checks asserted: none required.

Required markers intentionally left untested: none.

## Remaining Backlog

- Customer visual polish remains separate backlog work unless the release
  definition expands.
