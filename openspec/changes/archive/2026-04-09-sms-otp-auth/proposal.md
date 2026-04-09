## Why

Авторизация — первый блокер в MVP Phase 1 (§7.1). Без SMS OTP невозможны: оформление заказа, оплата, накопление баллов лояльности, отслеживание доставки. Все мутации состояния требуют серверной аутентификации (INV-002, INV-010), поэтому auth — фундамент для всех последующих фаз.

## What Changes

- Новые эндпоинты Core API: `POST /auth/send-code`, `POST /auth/verify-code`, `POST /auth/refresh`, `POST /auth/logout`
- OTP-генерация (6 цифр, cryptographically random) с хранением в Redis (`otp:{phone_hash}`, TTL 5 мин, max 5 попыток) — §6.4
- Rate-limiting отправки OTP в Core API: 1/мин, 5/час, 10/день — §6.4, §7.8
- Celery-задача в sms-worker для отправки SMS через SMS.ru (retry 3x с backoff 2s/8s/32s) — §7.8
- Создание пользователя при первой верификации OTP: `users` + `user_profiles` + `loyalty_accounts` — §6.5
- JWT-сессии (access + refresh tokens) с хранением refresh в Redis — §6.3
- Модели в shared: User, UserProfile, LoyaltyAccount + Alembic-миграция
- PII-изоляция: phone хранится зашифрованным (AES-256-GCM) в `user_profiles`, `phone_hash` (SHA-256) в `users` — INV-013

## Non-Goals

- Авторизация staff-аккаунтов (admin/barista/courier) — отдельный change, login/password flow (§6.5)
- Push-уведомления и email — только SMS в рамках этого change
- RBAC и role-based middleware — будет добавлен при реализации admin panel (Phase 6)
- Восстановление аккаунта / смена номера телефона — отдельный flow
- Frontend-реализация экранов авторизации — отдельный change для web-customer

## MVP Phase

**Phase 1: Auth** (§7.1) — данный change полностью покрывает customer auth из Phase 1.

## Capabilities

### New Capabilities

- `sms-otp`: OTP lifecycle — генерация, хранение в Redis, верификация, rate-limiting, интеграция с sms-worker (§6.4, §7.8)
- `customer-auth`: Customer-сессии — JWT access/refresh tokens, создание аккаунта при первой верификации, user state machine (§6.3, §6.5)
- `user-models`: Модели данных пользователя — users, user_profiles, loyalty_accounts, Alembic-миграция, PII-изоляция (INV-013)

### Modified Capabilities

_(нет изменений существующих спецификаций)_

## Impact

- **Core API** (`services/core-api/`): новый роутер `/auth`, middleware аутентификации, зависимости для current_user
- **SMS Worker** (`services/sms-worker/`): задача отправки OTP через SMS.ru API
- **Shared** (`packages/shared/`): модели User, UserProfile, LoyaltyAccount, enum-ы статусов
- **Database** (`database/`): Alembic-миграция для новых таблиц
- **Redis**: ключи `otp:{phone_hash}`, `session:{user_id}`, rate-limit counters
- **Зависимости**: PyJWT, cryptography (AES-256-GCM), httpx (SMS.ru API)
- **.env**: новые переменные — `SMS_RU_API_KEY`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `PII_ENCRYPTION_KEY` (INV-015)
