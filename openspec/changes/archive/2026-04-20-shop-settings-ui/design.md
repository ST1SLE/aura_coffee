## Context

**Module:** `[web-admin]`.

Сейчас `web/admin/src/pages/SettingsPage.tsx` — 12-строчный stub, а `shop_settings` редактируется только через SQL. Phase 6 item 3 (merge_order 3, `shop-settings-admin-api`) добавил FastAPI-эндпоинты `GET/PUT /api/v1/admin/settings` и новую колонку `auto_close_minutes` (миграция 0008). UI — парный тикет (merge_order 8, parallel_group 2).

В `web/admin` уже есть паттерн admin-CRUD формы с field-level-ошибками — `pages/Promos/PromoFormDialog.tsx`: native React-state, `authenticatedFetch`, `parseFieldErrors` от 422-ответа, `useNotifier` для toast'ов. Стек намеренно без `react-hook-form`/`zod` — их нет в `package.json`.

RBAC: на сервере `/api/v1/admin/settings` отдаёт 403 для barista/courier (спек `shop-settings-admin-api` + INV-010). На клиенте sidebar уже фильтрует ссылку (merge_order 1 — `admin-layout-rbac-wiring`), но для URL-ввода нужна защита на уровне маршрута. Сейчас `/settings` живёт внутри общей обёртки `ProtectedRoute allowedRoles={['admin','barista']}` — это позволит барист дойти до страницы, если она в sidebar не видна, но ввести URL можно.

Инвариант INV-010: ролевая изоляция серверная, но клиент SHALL помогать (`...и на клиенте, не показывать недоступные разделы...`). Делаем double-guard: inner `ProtectedRoute allowedRoles={['admin']}` вокруг `<SettingsPage/>`.

## Goals / Non-Goals

**Goals:**
- Админ видит full snapshot настроек, редактирует любое поле, сохраняет через PUT.
- Backend-валидация (422 с `detail[].loc`) маппится в field-level-ошибки в UI.
- Client-side валидация перед PUT ловит очевидные ошибки (`open ≥ close`, `101%`, `auto_close > 1440`, `free_delivery_threshold < min_delivery_amount`).
- `/settings` admin-only через inner `ProtectedRoute`, защита совпадает с серверной.
- i18n RU/EN для всех 10 полей + 7 дней недели + ошибки.

**Non-Goals:**
- Yandex-Maps-пикер для координат.
- Overnight-режим рабочих часов.
- PATCH/partial update.
- Audit-log редактирований (отдельный тикет).
- Кэширование клиентского ответа.

## Decisions

### D1. Native React state вместо react-hook-form + zod

**Почему:** в `web/admin/package.json` нет ни `react-hook-form`, ни `zod`. `PromoFormDialog` (merge_order 4 phase 5) использует `useState<FormState>` + manual submit-handler + `parseFieldErrors` — прецедент. Вводить новые зависимости ради одной страницы — premature. Task-prompt явно допускает native validation "как в PromoFormDialog".

**Альтернатива:** `react-hook-form` + `zod`. Плюс — schema-driven валидация, typed errors. Минус — +2 npm-deps, +bundle, другой ментальный паттерн для команды, изолированная схема параллельно Pydantic → double-source-of-truth.

### D2. Директория `pages/Settings/` вместо монолитного `SettingsPage.tsx`

**Почему:** форма делится на 5 семантических секций (coords, delivery, loyalty, timing, working_hours). Каждая — свой `.test.tsx` (task требует). Section-компоненты чистые (props: `value`, `onChange`, `errors`), контейнер `SettingsPage` держит общий state и submit-handler.

`pages/Settings/index.tsx` ре-экспортирует `SettingsPage`, `App.tsx` импортирует `@/pages/Settings` — чистый импорт.

Оригинальный stub `pages/SettingsPage.tsx` удаляется; если внешние модули импортировали `@/pages/SettingsPage` — перенаправим на `@/pages/Settings`.

### D3. Kopecks ↔ Rubles конверсия — helper в `api/admin-settings.ts`

**Почему:** API-слой — единственное место, где мы знаем, что поля денег хранятся в копейках. UI работает с рублями (UX). Helper `toKopecks(rubles: number): number` / `kopecksToRubles(k: number): string` (дробь → 2 знака). Та же функция используется в `PromoFormDialog`; переносить в общий `lib/money.ts` — premature (всего 2 места).

Поля в копейках: `min_delivery_amount`, `free_delivery_threshold`, `delivery_fee`. Поля НЕ-денежные: `delivery_radius_km` (число с точкой, `numeric`), `loyalty_percent`, `*_minutes`, `shop_lat/lon`.

### D4. PUT full snapshot, не PATCH

**Почему:** спек `shop-settings-admin-api` (phase 6 plan, merge_order 3) явно запрещает PATCH: `"НЕ вводить PATCH (только PUT full-snapshot — избегаем JSONB merge)"`. UI отдаёт весь state в payload. Если пользователь не редактировал часть полей — присылаются initial values из `getSettings()`.

### D5. 422-маппинг: `parseFieldErrorsDeep`

**Почему:** `parseFieldErrors` в `api/promocodes.ts` берёт только last-segment `loc` — для плоских форм. Наш payload вложенный: `loc=['body','working_hours','mon','open']` → field-path `working_hours.mon.open`. Нужен deep-параlatestser. Добавляем в `api/admin-settings.ts` функцию `parseFieldErrorsDeep(err) → Record<string, string>`, где ключ — `"working_hours.mon.open"`, `"free_delivery_threshold"`, и т. п. UI сопоставляет по этим ключам.

### D6. Save-button gating через `isDirty` + `isValid`

**Почему:** task-prompt: "Save disabled пока isDirty=false || !isValid". 
- `isDirty` — сравнение текущего `form` с `initialForm` (deep-equal по референсу через сериализацию JSON).
- `isValid` — результат client-side validate-функции (агрегирующей результаты каждой секции).

Cron-рев / autosave не делаем — задача явно не просит.

### D7. Double-guard на `/settings`

**Почему:** INV-010 требует и клиентского, и серверного enforcement. Сервер проверяет в rbac_matrix (уже есть). Клиент: sidebar-filter (уже) + inner `ProtectedRoute allowedRoles={['admin']}`. Барист, набирая URL, гарантированно редиректится.

**Альтернатива:** вынести `/settings` из общей admin+barista-обёртки в отдельную admin-only-обёртку на уровне `Routes`. Минус — дублирует `Layout` wrapper. Inner-wrap проще.

### D8. После 200 — refetch через `getSettings()`

**Почему:** backend возвращает full `ShopSettingsResponse` в PUT-ответе с новым `updated_at`. Но task-prompt: "НЕ кэшировать settings — после save refetch для корректности updated_at". Выполняем refetch как doubling — отбрасываем PUT-ответ и читаем заново. Это сброс `isDirty` → initial = новый response.

Практически: `setInitialForm(resp); setForm(fromResponse(resp))`. Не делаем separate `getSettings()` — PUT-response достаточен; task-prompt "refetch" интерпретируем как "обновить initial с ответа сервера, не полагаться на локальный snapshot". Если команда эксплицитно хочет отдельный GET — легко поменять.

## Risks / Trade-offs

- **[Risk] Stale backend-dep:** эта ветка форкнута от `admin_ui_phase`, в котором `shop-settings-admin-api` формально не merged (merge_order 3 ещё не произошёл в orchestrator'е). → **Mitigation:** реализуем UI против документированного контракта из `docs/phase6-plan.yaml` строк 360–506 + существующего `schemas/shop_settings.py`. Интеграционные тесты страницы мокают `fetch`. Итоговый merge произойдёт только после merge_order 3, consistency гарантирована orchestrator'ом.
- **[Trade-off] Deep-parse 422 без типизации детальных полей:** `Record<string, string>` не типизирован — опечатка в ключе `"working_hours.mon.opem"` не ловится компилятором. → **Mitigation:** const-коллекция валидных field-ключей в начале `SettingsPage.tsx`; тест проверяет соответствие ключей схеме. Типизировать `Record<SettingsFieldPath, string>` с union — over-engineering для 10 полей.
- **[Risk] Race при одновременном редактировании двумя админами:** второй PUT перезапишет первый (last-write-wins). → **Mitigation:** вне scope (отдельный тикет optimistic-concurrency через `If-Match`/`updated_at`). Singleton + редкая мутация → low-risk.
- **[Trade-off] Client validation дублирует backend:** те же границы проверяются на сервере. → **Mitigation:** UX — мгновенная обратная связь без сетевого roundtrip. Sync обеспечивается ссылкой на PDD §5.2 в обоих местах. При расхождении сервер всё равно authoritative (видим 422).

## Migration Plan

Код-only, без БД-миграций (миграция 0008 — в `shop-settings-admin-api`). Deploy-последовательность:

1. merge `shop-settings-admin-api` (order 3) → backend готов.
2. merge `shop-settings-ui` (order 8) → UI.
3. Rollback: revert UI-коммит. Backend остаётся работоспособным (CLI/SQL-доступ сохраняется).
4. Feature-flag не нужен — нет частичной доступности; `/settings` либо работает, либо `NotFoundPage` (при ручном откате роута).

## Open Questions

Нет.
