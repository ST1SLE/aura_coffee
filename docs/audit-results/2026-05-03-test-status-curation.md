# Aura Coffee Test Status Curation

Date: 2026-05-03

Source: `docs/audit-results/2026-05-02-verification-audit.md` P2,
"Stale/flaky-test signal is not curated".

## Scope

This packet handles the backend PyJWT warning slice only:

- dated status split between historical audit logs and current checks;
- deterministic Core API test JWT secret with at least 32 characters;
- focused proof that token-heavy Core API tests no longer emit
  `jwt.warnings.InsecureKeyLengthWarning`.

Frontend React `act(...)` warnings, Radix Dialog description warnings, and the
frontend stderr warning gate were handled in the follow-up
`docs/audit-results/2026-05-03-frontend-warning-curation.md` packet.

## Current Status

Historical logs under `docs/audit-results/` are snapshots from previous audit
runs. They are useful evidence, but they are not the current release gate.

The recurring PyJWT warning came from test token helpers and from the running
Core API container's local placeholder `JWT_SECRET_KEY` value
`change-me-to-random-secret`, which is only 26 characters. Core API tests now
force a deterministic test-only secret before importing the app:

```text
aura-coffee-tests-jwt-secret-0001
```

The same secret is used by explicit token helpers in route and service tests
that patch auth settings directly. The weak values in
`services/core-api/tests/test_settings_safety_rail.py` are intentionally
preserved because they are negative validation fixtures and do not mint JWTs.
`services/core-api/tests/test_delivery_addresses_api.py` already uses a
40-character test secret, so it was left unchanged.

## Verification

Commands run for this packet:

```bash
docker compose exec -T core-api pytest \
  services/core-api/tests/test_customer_notifications.py \
  services/core-api/tests/test_admin_orders_list.py \
  services/core-api/tests/test_route_cart.py::test_post_cart_item_merges_same_line \
  services/core-api/tests/test_route_cart.py::test_patch_cart_item_updates_quantity \
  services/core-api/tests/test_route_cart.py::test_delete_cart_item_removes_line \
  services/core-api/tests/test_route_cart.py::test_cart_ttl_env_override_respected \
  services/core-api/tests/test_route_orders.py::test_post_orders_requires_auth \
  services/core-api/tests/test_route_order_actions.py \
  services/core-api/tests/test_courier_endpoints.py \
  services/core-api/tests/test_jwt.py \
  -W error::jwt.warnings.InsecureKeyLengthWarning -q
# 78 passed

docker compose exec -T core-api pytest \
  services/core-api/tests/test_staff_auth.py \
  services/core-api/tests/test_token_lifecycle.py \
  services/core-api/tests/test_delivery_addresses_api.py \
  -W error::jwt.warnings.InsecureKeyLengthWarning -q
# 67 passed; only unrelated deprecation warnings were reported

docker compose exec -T core-api ruff check \
  services/core-api/tests/conftest.py \
  services/core-api/tests/_helpers/jwt.py \
  services/core-api/tests/test_route_cart.py \
  services/core-api/tests/test_route_orders.py \
  services/core-api/tests/test_route_order_actions.py \
  services/core-api/tests/test_checkout_delivery_address_id.py \
  services/core-api/tests/test_profile_endpoints.py \
  services/core-api/tests/test_rbac_middleware.py \
  services/core-api/tests/test_courier_endpoints.py \
  services/core-api/tests/test_jwt.py
# All checks passed
```

## GRACE/LDD

LDD assertions are not required for this packet. It changes test-only JWT
fixtures and audit documentation, with no runtime auth behavior, role checks,
state transitions, transaction boundaries, production secrets, PII paths, or
logging paths changed.

Markers asserted: none.

Redaction checks asserted: none required.

Required markers intentionally left untested: none.

## Remaining Curation Backlog

- No stale/flaky warning curation backlog remains from this P2 item.
