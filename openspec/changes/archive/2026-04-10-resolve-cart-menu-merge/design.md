## Context

**Affected modules:** [core-api].

Three feature branches landed Phase 2 work in sequence on `menu_cart`:

```
    menu_cart (HEAD)
    ┌──────────────────────────────────────┐
    │  menu-admin-crud     (merged earlier)│
    │  menu-public-read    (merged earlier)│
    │  ← aura_coffee-cart  (merging NOW)   │
    └──────────────────────────────────────┘
```

`git merge aura_coffee-cart` produced three textual conflicts plus one hidden semantic conflict:

| File | Flagged by git? | Kind |
|------|-----------------|------|
| `services/core-api/src/core_api/rbac_matrix.py` | YES | both sides added new routes in the same dict literal |
| `services/core-api/tests/conftest.py` | YES | both sides added new fixtures in the same region |
| `services/core-api/tests/test_router_stubs.py` | YES | both sides shrunk the same `stub_files` list from different directions |
| `services/core-api/tests/test_main_includes_menu_routers.py` | **NO** | auto-merged to the `aura_coffee-cart` version, but that version asserts empty menu paths — HEAD has populated both menu routers |

All four are **merge-state bookkeeping**, not feature work. The `cart-api`, `menu-public-read`, and `menu-admin-crud` capabilities themselves are untouched.

Prior verification (explore session) confirmed:
- `shared/models/menu.py` and `shared/enums.py` are byte-identical on both branches.
- `deps/database.py` auto-merged cleanly; `aura_coffee-cart` added a `get_session = get_db` alias that cart code patches in tests.
- No fixture name collisions between the HEAD and `aura_coffee-cart` conftest additions.
- Module-local `client`/`db_client` in `test_route_cart.py` shadow the conftest-level ones correctly via pytest scoping.
- `main.py` currently has exactly 6 `include_router(` calls, matching the `count == 6` assertion in `test_main_include_router_call_count`.

## Goals / Non-Goals

**Goals:**

- Produce a single commit that finishes the merge and leaves `pytest services/core-api/` green on both sqlite and Postgres modes.
- Correct the latent semantic failure in `test_main_includes_menu_routers.py` that git could not detect.
- Retire the obsolete stub-state requirements in the `menu-router-stubs` capability so specs match code.
- Preserve every route, fixture, and requirement added by either side — this is a union resolution, not a rewrite.

**Non-Goals:**

- No refactor of duplicate test infrastructure (`db_client` in conftest vs. `test_route_cart.py`, `_pg_ready` vs. `db_session` both running `alembic upgrade head`). Redundant but correct — cleanup belongs to a future change.
- No reordering or renaming of routes, fixtures, or requirements. Union only.
- No archival of the `menu-router-stubs` capability as a whole — the populated `menu_admin` requirement stays.
- No new tests. This change exists to unblock the merge, not to add coverage.

## Decisions

### Decision 1: Resolve `rbac_matrix.py` as a plain union

Both sides added disjoint dict entries to `ROUTE_MATRIX`. HEAD added menu-admin CRUD routes (15 entries across categories/items/modifiers/sizes); `aura_coffee-cart` added 5 cart routes bound to `{CUSTOMER}`. The merged file MUST contain every entry from both sides, with conflict markers removed. Comment headers from both sides SHALL be preserved so the dict stays readable. Order within the dict is informational only — Python dict equality is key-based.

**Alternative considered:** sort the matrix alphabetically during the merge. Rejected — mixes unrelated cleanup into a merge commit and makes the diff harder to review.

### Decision 2: Resolve `conftest.py` as a plain union

The HEAD additions (`PublicMenuSeed` dataclass, `_pg_ready` session fixture, `_pg_db_override` function fixture, `seed_public_menu` fixture, plus the module-level sqlite `StaticPool` block) and the `aura_coffee-cart` additions (`cart_redis` fixture, `db_session` fixture) live in disjoint regions with no shared identifiers. The resolution SHALL keep both blocks verbatim, with conflict markers removed and the HEAD block placed before the `aura_coffee-cart` block (current textual order in the conflict). A single top-level docstring/comment banner SHALL separate the two regions for readability.

**Why keep redundant alembic-upgrade machinery:** `_pg_ready` (session-scoped) and `db_session` (function-scoped, calls `command.upgrade` on every invocation) are both idempotent. Collapsing them is a cleanup worth doing, but not in a merge resolution commit — it widens blast radius for no functional gain.

### Decision 3: Delete `test_router_stubs.py` entirely

Post-merge, `stub_files` collapses to `[]`, which makes `test_stubs_have_no_endpoint_decorators` a loop over an empty list — a silent no-op. The three surviving `*_router_exists` assertions only check `isinstance(router, APIRouter)`, `router.prefix`, and `router.tags`, all of which are trivially covered by the real route tests (`test_route_cart.py`, the menu admin tests, the menu public tests) that exercise every endpoint via `TestClient`.

The file was explicitly RED-phase scaffolding — its docstring says so: *"Тесты 7.1–7.3 ДОЛЖНЫ падать с ImportError до создания файлов."* It served its purpose during stub bootstrap and is dead weight now.

**Alternative considered:** keep the file with `stub_files = []` and the three `*_router_exists` assertions. Rejected — the module then exists only to duplicate checks already present elsewhere, and future readers have to re-derive "why is this here" every time. Deletion is the honest move.

**Alternative considered:** keep only the three `*_router_exists` checks and drop `test_stubs_have_no_endpoint_decorators`. Rejected for the same reason — the remaining checks are already covered.

### Decision 4: Surgical fix for `test_main_includes_menu_routers.py`

Delete only the loop asserting empty paths under `/api/v1/admin/menu` and `/api/v1/menu`:

```python
# DELETE THESE LINES:
for prefix in ("/api/v1/admin/menu", "/api/v1/menu"):
    matching = [p for p in paths if p.startswith(prefix)]
    assert matching == [], ...
```

Keep:
- The tag-presence check (`menu-admin`, `menu-public`, `cart` tags in OpenAPI) — still a valid smoke test.
- `test_main_include_router_call_count` — `main.py` has exactly 6 `include_router(` calls, matches the assertion.

Update the module docstring to drop the "RED" framing, since the file is now a post-GREEN smoke test.

**Why not delete the file entirely too:** the `include_router count == 6` check is the only remaining place that asserts `main.py` hasn't regrown duplicate or conditional router mounts. Worth keeping until a larger test-hygiene pass.

### Decision 5: Retire three obsolete requirements in `menu-router-stubs` spec

The `menu-router-stubs` spec currently asserts:
1. `menu_admin` router is populated and mounted ← **KEEP**
2. Empty `menu_public` router stub exists and is mounted ← **REMOVE** (superseded by `menu-public-read`)
3. Empty `cart` router stub exists and is mounted ← **REMOVE** (superseded by `cart-api`)
4. `main.py` registers all three routers exactly once ← **KEEP** (still a useful invariant; matches test 7.6)
5. Endpoint-free constraint applies only to `menu_public` and `cart` ← **REMOVE** (both are now populated)

The delta spec file for this change SHALL use `## REMOVED Requirements` to retire requirements 2, 3, and 5. Requirement 1 and 4 stay authoritative.

**Why not archive the capability entirely:** requirement 1 ("menu_admin is populated and mounted") and requirement 4 ("exactly-once include") still carry weight — they guard against main.py regressions. Killing the capability would lose that coverage.

## Risks / Trade-offs

- **[Risk]** The merge resolution touches three test files and one runtime file. A mistake in `rbac_matrix.py` (missing an entry from either side) silently drops RBAC coverage. **Mitigation:** after resolution, run `pytest services/core-api/tests/test_rbac_matrix.py -v` — the `TestCartRbac` class (added by `aura_coffee-cart`) and the menu admin route checks both verify their entries are present.

- **[Risk]** Deleting `test_router_stubs.py` removes a module that future contributors might expect to find when debugging router mount issues. **Mitigation:** the deletion is recorded in this change's proposal and tasks; the `menu-router-stubs` spec delta explains the rationale; `test_main_includes_menu_routers.py` retains the `include_router count == 6` check as the surviving smoke test.

- **[Trade-off]** The merged conftest carries two parallel Postgres-bootstrap paths (`_pg_ready`/`_pg_db_override` for menu tests, `db_session` for cart tests). Running the full suite against Postgres runs `alembic upgrade head` more times than strictly needed. Accepted as-is — collapsing them would widen the merge commit's surface area and is easy to do later as a test-infra cleanup.

- **[Risk]** Git recorded `test_main_includes_menu_routers.py` as a clean auto-merge. A reviewer skimming the merge commit will not see it in the conflict list, yet this change touches it. **Mitigation:** the tasks file calls it out explicitly and the commit message (when applied) MUST mention all four files, not just the three git flagged.

## Migration Plan

This is a merge-completion change, not a deployment. No runtime migration, no DB migration, no data backfill.

Apply order:
1. Fix the four files listed above.
2. Update the spec delta (`openspec/changes/resolve-cart-menu-merge/specs/menu-router-stubs/spec.md`).
3. Run `pytest services/core-api/` on sqlite (fast). Expect: all green, Postgres-only tests skipped.
4. Run `pytest services/core-api/` with `TEST_DATABASE_URL` set (slow). Expect: all green including menu public seed tests and cart DB tests.
5. `git add` the resolved files and `git commit` — creating the merge commit.
6. Archive this change once the merge commit lands.

**Rollback:** `git merge --abort` aborts the whole merge. This change carries no post-merge residue — rolling back the merge rolls back the resolution automatically.

## Open Questions

None. The verification pass confirmed all assumptions; the four resolutions are mechanical and the spec delta is a clean removal of obsolete requirements.
