## Why

`web-customer` container mounts only `./web/customer:/app`, but `tailwind.config.ts` requires `../shared-config/tailwind-preset` which resolves to a path outside the mount. CSS compilation fails with `Cannot find module '../shared-config/tailwind-preset'`, rendering the customer frontend unusable (white screen / no styles). This blocks all Phase 1 frontend testing.

## What Changes

- Mount `web/shared-config` into `web-customer` container so the Tailwind preset is accessible at build time
- Apply the same fix to `web-admin` if it uses the same preset (preventive)

## Non-Goals

- Restructuring the shared-config module or changing import paths in application code
- Fixing nginx startup race condition (separate issue)
- Fixing sms-worker task discovery (separate issue)

## Capabilities

### New Capabilities

_None — this is an infrastructure/config fix, no new application capabilities._

### Modified Capabilities

_None — no spec-level behavior changes, only Docker volume configuration._

## Impact

- **File**: `docker-compose.yml` — volume mounts for `web-customer` and `web-admin` services
- **Phase**: Phase 1 (Auth & User Profile) — unblocks frontend testing
- **Risk**: Low — only changes local dev container mounts, no application code changes
