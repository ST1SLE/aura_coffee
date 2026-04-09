## 1. Backend — Pydantic Schemas

- [x] 1.1 [core-api] Create `schemas/profile.py` with `ProfileResponse` (user_id, phone_masked, display_name, preferred_language) and `ProfileUpdateRequest` (display_name: Optional[str], preferred_language: Optional[Literal["ru", "en"]])

## 2. Backend — Profile Service

- [x] 2.1 [core-api] Create `services/profile.py` with `get_profile(user_id, db)` — query `user_profiles`, decrypt phone, mask it, return `ProfileResponse`
- [x] 2.2 [core-api] Add `update_profile(user_id, data, db)` to `services/profile.py` — partial update of `display_name` and/or `preferred_language` on `user_profiles`, return updated `ProfileResponse`

## 3. Backend — Profile Router

- [x] 3.1 [core-api] Create `routers/profile.py` with `GET /api/v1/profile` endpoint — require JWT auth with role `customer`, call `get_profile`, return 200/401/403/404
- [x] 3.2 [core-api] Add `PATCH /api/v1/profile` endpoint to `routers/profile.py` — require JWT auth with role `customer`, validate body, call `update_profile`, return 200/401/403/422
- [x] 3.3 [core-api] Register `profile_router` in `main.py`

## 4. Backend — Tests

- [x] 4.1 [core-api] Add tests for `GET /api/v1/profile` — authenticated success, masked phone format, 401 unauthenticated, 403 wrong role, 404 missing profile
- [x] 4.2 [core-api] Add tests for `PATCH /api/v1/profile` — update name, update language, partial update, empty body no-op, validation errors (name too long, invalid language)

## 5. Frontend — API Client

- [x] 5.1 [web-customer] Regenerate API client from updated OpenAPI spec (or add profile API functions manually if generator not yet wired)

## 6. Frontend — Profile Page

- [x] 6.1 [web-customer] Create `pages/ProfilePage.tsx` — fetch profile on mount, display masked phone (read-only), editable display name, language switcher (RU/EN)
- [x] 6.2 [web-customer] Add profile update handler — `PATCH /api/v1/profile` on save, update i18next language on language change
- [x] 6.3 [web-customer] Add loading and error states to `ProfilePage` — spinner on fetch, error message with retry

## 7. Frontend — Routing

- [x] 7.1 [web-customer] Add `/profile` route behind auth guard in router config
- [x] 7.2 [web-customer] Add profile link/navigation entry to the app layout (header or menu)

## 8. Frontend — i18n

- [x] 8.1 [web-customer] Add profile page translation keys to RU and EN locale files (page title, labels, buttons, error messages)
