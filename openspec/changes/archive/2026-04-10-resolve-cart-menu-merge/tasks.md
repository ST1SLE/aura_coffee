## 1. Resolve textual merge conflicts

- [x] 1.1 Resolve `services/core-api/src/core_api/rbac_matrix.py`: remove `<<<<<<<`/`=======`/`>>>>>>>` markers; keep both the menu-admin route block (HEAD) and the cart route block (`aura_coffee-cart`) as a union. Preserve the section-header comments from both sides.
- [x] 1.2 Resolve `services/core-api/tests/conftest.py`: remove conflict markers; keep the HEAD block (`PublicMenuSeed` dataclass, `_pg_ready`, `_pg_db_override`, `seed_public_menu`) followed by the `aura_coffee-cart` block (`cart_redis`, `db_session`). Verify no fixture name is defined twice.
- [x] 1.3 Delete `services/core-api/tests/test_router_stubs.py` entirely (via `git rm`). The file is RED-phase scaffolding superseded by full route tests for cart, menu admin, and menu public.

## 2. Fix hidden semantic conflict

- [x] 2.1 Edit `services/core-api/tests/test_main_includes_menu_routers.py`: remove the `for prefix in ("/api/v1/admin/menu", "/api/v1/menu"):` loop and its `assert matching == []` body. Keep the tag-presence check above it and `test_main_include_router_call_count` below it.
- [x] 2.2 Update the module docstring at the top of `test_main_includes_menu_routers.py` to drop the "RED" framing — the file now runs as a post-GREEN smoke test.

## 3. Update spec

- [x] 3.1 Verify `openspec/changes/resolve-cart-menu-merge/specs/menu-router-stubs/spec.md` exists and removes requirements *"Empty menu_public router stub exists and is mounted"*, *"Empty cart router stub exists and is mounted"*, and *"Endpoint-free constraint applies only to menu_public and cart"* with `REMOVED Requirements` blocks.
- [x] 3.2 Confirm the surviving requirements *"menu_admin router is populated and mounted"* and *"main.py registers all three routers exactly once"* are NOT listed in the delta spec (they remain untouched).

## 4. Validate

- [x] 4.1 Run `pytest services/core-api/` on sqlite (no `TEST_DATABASE_URL`). Expect: all green; Postgres-only tests (menu admin integration, cart DB tests, public menu seeded tests) skipped.
- [ ] 4.2 Run `pytest services/core-api/` with `TEST_DATABASE_URL` exported. Expect: all green including `test_route_cart.py`, `test_cart_service.py`, and the `seed_public_menu` tests.
- [x] 4.3 Run `pytest services/core-api/tests/test_rbac_matrix.py -v` specifically and confirm both `TestCartRbac` (added by `aura_coffee-cart`) and the existing menu-admin route checks pass.
- [x] 4.4 Run `grep -c "include_router(" services/core-api/src/core_api/main.py` and confirm the count is `6`, matching `test_main_include_router_call_count`.
- [x] 4.5 Run `openspec validate resolve-cart-menu-merge --strict` and confirm the change passes.

## 5. Finalize merge

- [x] 5.1 `git status` — confirm no files remain in `UU` (unmerged) state.
- [x] 5.2 `git add` the four resolved files (`rbac_matrix.py`, `conftest.py`, `test_main_includes_menu_routers.py`) and stage the deletion of `test_router_stubs.py`.
- [x] 5.3 Show the user the draft merge commit message summarizing all four files (including `test_main_includes_menu_routers.py`, which git did not flag) and wait for explicit approval before running `git commit`.
- [x] 5.4 After approval, create the merge commit. Do NOT push.

## 6. Archive change

- [ ] 6.1 After the merge commit lands and the suite is green, archive this change via the `openspec-archive-change` workflow so the `menu-router-stubs` spec delta is applied to `openspec/specs/menu-router-stubs/spec.md`.
