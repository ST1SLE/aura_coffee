## 1. Schemas

- [x] 1.1 GREEN [core-api] Add `PublicMenuSizeOption` to `services/core-api/src/core_api/schemas/menu.py` with fields `id: int`, `label: SizeLabel`, `price: int = Field(ge=0)`, `available: bool`, and `model_config = ConfigDict(from_attributes=True)` → passes 3.1, 3.7.
- [x] 1.2 GREEN [core-api] Add `PublicMenuModifier` to the same file with fields `id: int`, `name: str`, `name_ru: str`, `name_en: str`, `price: int = Field(ge=0)`, `available: bool`, `from_attributes=True` → passes 3.1, 3.6.
- [x] 1.3 GREEN [core-api] Add `PublicMenuItem` to the same file: no `archived`, no `availability`; includes `id`, `category_id`, `name`, `name_ru`, `name_en`, `description`, `description_ru`, `description_en`, `base_price` (ge=0), `image_url: str | None`, `available: bool`, `sort_order: int`, `size_options: list[PublicMenuSizeOption] = []`, `modifiers: list[PublicMenuModifier] = []`, `from_attributes=True` → passes 3.1, 3.2, 3.3.
- [x] 1.4 GREEN [core-api] Add `PublicCategory` with fields `id`, `type: CategoryType`, `name`, `name_ru`, `name_en`, `sort_order: int`, `items: list[PublicMenuItem] = []`, `from_attributes=True` → passes 3.1, 3.4.
- [x] 1.5 GREEN [core-api] Add `PublicMenuResponse` with `categories: list[PublicCategory] = []` → passes 3.1, and 4.1/4.2 response shape.
- [x] 1.6 REFACTOR [core-api] Within `schemas/menu.py`, group all `Public*` schemas under one commented section header (RU, 1 line); verify `test_schemas_menu.py` still green and that `test_admin_menu_item_response_still_has_archived` (3.5) still passes. No behavior change.

## 2. Service — Language enum and signature

- [x] 2.1 GREEN [core-api] In `services/core-api/src/core_api/services/menu_public.py`, define `class Language(str, Enum): RU = "ru"; EN = "en"` → passes 2.3.
- [x] 2.2 GREEN [core-api] Define `def get_public_menu(db: Session, *, only_available: bool, language: Language) -> PublicMenuResponse:` stub body that returns `PublicMenuResponse(categories=[])` → passes 2.1, 2.2.

## 3. Service — query and visibility rules

- [x] 3.1 GREEN [core-api] Inside `get_public_menu`, build the SQLAlchemy 2.0 `select(Category)` query: filter `Category.is_visible.is_(True)`, `Category.type != CategoryType.MODIFIER`, order by `Category.sort_order, Category.id`. Eager-load items via `selectinload(Category.menu_items.and_(MenuItem.archived.is_(False)))`; chain `selectinload(MenuItem.size_options)` and `selectinload(MenuItem.modifiers)`. Execute once. → satisfies query-shape aspects of 9.2.
- [x] 3.2 GREEN [core-api] In the same function, when `only_available` is `True` apply Python-side pruning on the loaded tree: drop items whose `available is False`, and for each remaining item filter its `size_options` to `available is True`. Modifiers are NOT filtered. → passes 6.2, 6.3, 8.3.
- [x] 3.3 GREEN [core-api] Still inside `get_public_menu`, after fetching, sort each item's `size_options` by enum order of `SizeLabel` (`S`, `M`, `L`) via an explicit key function and sort each item's `modifiers` by `(sort_order, id)`. → passes 8.1, 8.2.

## 4. Service — bilingual projection

- [x] 4.1 GREEN [core-api] Add a private helper `def _pick(language: Language, ru: str | None, en: str | None) -> str | None: return en if language is Language.EN else ru` in `services/menu_public.py`. Unit-exercised indirectly by the router tests.
- [x] 4.2 GREEN [core-api] In `get_public_menu`, map each ORM `MenuItem` to `PublicMenuItem` by calling `_pick` for `name` and `description`, keeping the raw `*_ru` / `*_en` fields untouched. → passes 7.1, 7.2, 7.5.
- [x] 4.3 GREEN [core-api] In the same mapping pass, map each `Modifier` to `PublicMenuModifier` with bilingual `name` projected via `_pick`. → passes 7.6.
- [x] 4.4 GREEN [core-api] Map each `Category` to `PublicCategory` with `name` projected via `_pick` and the embedded `items` list built from the mapping above. → passes 7.1, 7.2.
- [x] 4.5 REFACTOR [core-api] Collapse the three mapping passes (category, item, modifier) into one top-down function composition in `get_public_menu`. No behavior change — rerun the full service + HTTP test suite to confirm still green.

## 5. Router — HTTP endpoint

- [x] 5.1 GREEN [core-api] In `services/core-api/src/core_api/routers/menu_public.py`, add a module-level helper `def _parse_language(header: str | None) -> Language:` that returns `Language.EN` iff `header` (trimmed, lowered) starts with `"en"`, else `Language.RU`. → passes 7.1, 7.2, 7.3, 7.4.
- [x] 5.2 GREEN [core-api] Add `@router.get("", response_model=PublicMenuResponse)` handler `def get_menu(...)`, declaring parameters: `db: Session = Depends(get_db)`, `available: bool | None = Query(None)`, `accept_language: str | None = Header(None, alias="Accept-Language")`. Body delegates to `menu_public_service.get_public_menu(db, only_available=bool(available), language=_parse_language(accept_language))` and returns its result directly. → passes 4.1, 4.2, 4.3, 5.x, 6.x, 9.3.
- [x] 5.3 GREEN [core-api] Add `("GET", "/api/v1/menu")` to `PUBLIC_ROUTES` in `services/core-api/src/core_api/rbac_matrix.py` so anonymous requests bypass the RBAC middleware. → enables tests 4.1, 4.2, and all HTTP tests that assert status 200 for unauthenticated clients.
- [x] 5.4 GREEN [core-api] Confirm no `Depends(get_current_user)` / RBAC decorator is added to the handler, and do NOT add any entry to `ROUTE_MATRIX` referencing `/api/v1/menu` with method `GET` (only `PUBLIC_ROUTES` entry is correct). → passes 9.1.

## 6. Cleanup after router changes

- [x] 6.1 REFACTOR [core-api] Review `routers/menu_public.py` for imports and drop any that went unused. Re-run `pytest services/core-api/tests/test_menu_public.py -x` and confirm all green.
- [x] 6.2 REFACTOR [core-api] Re-run `pytest services/core-api/tests/test_router_stubs.py -x` to confirm the updated stub assertions from RED 10.1 now pass against the filled-in router.

## 7. Verify

- [x] 7.1 VERIFY [core-api] Run full core-api test suite: `pytest services/core-api/tests -x`. Expected: all tests pass, including the new `test_menu_public.py`, the amended `test_router_stubs.py`, and every pre-existing test in the service. Capture the green summary.
- [x] 7.2 VERIFY [core-api] Boot the app via `TestClient(app)` in a throwaway script and fetch `/openapi.json`; assert manually that `/api/v1/menu` is present under the `menu-public` tag with a single `GET` operation and that the response schema references `PublicMenuResponse`. This is the contract the frontend API-client generator will consume.
- [x] 7.3 VERIFY [core-api] Run `pytest services/core-api/tests/test_menu_public.py::test_public_menu_query_is_bounded -x` in isolation to confirm the statement count (9.2) stays within the `<= 4` budget — guards against accidental lazy loads introduced during REFACTOR passes.
- [x] 7.4 VERIFY [core-api] Hit `GET /api/v1/menu` through the running dev stack (`services/core-api` container) with `curl -H "Accept-Language: en"` and again with `-H "Accept-Language: ru"`; confirm the `name` fields differ and the raw `name_ru`/`name_en` pairs match between the two responses. Document the two payloads in the task output. This is an end-to-end smoke check on top of the unit/integration tests.
