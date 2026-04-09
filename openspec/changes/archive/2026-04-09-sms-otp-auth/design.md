## Affected Modules

`[core-api]` `[sms-worker]` `[shared]` `[database]` `[redis]`

## Context

Aura Coffee — greenfield, база пуста (только `DeclarativeBase`). Это первый change в Phase 1 (§7.1). Инфраструктура (Docker, Redis, PostgreSQL, Celery) уже scaffold'ирована, но рабочего кода нет. SMS Worker имеет только health_check таску.

Авторизация клиентов — SMS OTP (§6.4). Персонал авторизуется отдельно (login/password) — вне scope этого change.

## Goals / Non-Goals

**Goals:**
- Реализовать полный OTP lifecycle (§6.4): CREATED → SENT → VERIFIED/EXPIRED/FAILED
- Реализовать user account lifecycle (§6.5): PENDING_VERIFICATION → ACTIVE (только этот переход в scope)
- Реализовать JWT-сессии (access + refresh) для customer auth
- Обеспечить PII-изоляцию (INV-013) и 152-ФЗ compliance
- Обеспечить rate-limiting OTP (INV-012)

**Non-Goals:**
- Staff auth (login/password) — отдельный change
- RBAC middleware — отдельный change
- BLOCKED/DELETED transitions для user account — будут в admin panel change
- Frontend screens — отдельный change

## Decisions

### D1: OTP хранение — Redis String с JSON payload

**Решение:** `otp:{phone_hash}` хранит JSON `{"code": "123456", "attempts": 0, "status": "CREATED"}` с TTL 300s.

**Альтернатива:** Отдельные ключи для code/attempts/status. Отвергнута — атомарность обновления требует единого ключа (race condition при параллельных verify-запросах).

**Атомарность:** Все операции с OTP (проверка + инкремент attempts) MUST использовать Lua-скрипт в Redis для atomicity.

### D2: Rate-limiting — Redis INCR + TTL counters

**Решение:** Три ключа per phone_hash (§5.3, INV-012):
- `sms_rate:{phone_hash}:min` — TTL 60s
- `sms_rate:{phone_hash}:hour` — TTL 3600s  
- `sms_rate:{phone_hash}:day` — TTL 86400s

Операция: `INCR` + `EXPIRE` (только если ключ новый). Проверка ДО создания OTP.

**Альтернатива:** Sliding window (ZSET). Отвергнута — overengineering для текущих лимитов (1/5/10), fixed window достаточен.

### D3: JWT — access token (short-lived) + refresh token (Redis-backed)

**Решение:**
- Access token: JWT, подписан HS256, TTL 15 мин. Payload: `{sub: user_id, role: "customer", iat, exp}`. Stateless — не хранится в Redis.
- Refresh token: opaque UUID, хранится в Redis `session:{refresh_token}` с TTL 7 дней (§5.3). Value: JSON `{user_id, issued_at}`.
- Refresh endpoint выдаёт новую пару access+refresh (rotation).

**Альтернатива:** Только access token с длинным TTL. Отвергнута — компрометация одного токена даёт длительный доступ, rotation снижает risk window.

**Альтернатива:** RS256 (asymmetric). Отвергнута — единственный consumer (core-api) = symmetric достаточен, проще key management.

### D4: Phone hashing — SHA-256 без соли

**Решение:** `phone_hash = SHA256(normalized_phone)` где normalized = `+7XXXXXXXXXX` (E.164). Без соли — нужен детерминированный lookup (§5.2).

**Обоснование:** PDD явно указывает "SHA-256, без соли — нужен детерминированный поиск" (§5.2 примечания).

### D5: Phone encryption — AES-256-GCM

**Решение:** `user_profiles.phone` шифруется AES-256-GCM. Ключ — `ENCRYPTION_KEY` из env (INV-015, §8.4). Unique nonce per record.

### D6: SMS Worker интеграция — Celery task с retry

**Решение:** Core API ставит задачу `send_otp_sms.delay(phone_hash, code)`. SMS Worker:
1. Расшифровывает phone из user_profiles (или получает phone как аргумент задачи)
2. Отправляет через SMS.ru `POST /sms/send`
3. При успехе — обновляет OTP status → SENT в Redis
4. При ошибке — retry 3x с backoff 2s/8s/32s (§7.8)
5. При исчерпании retries — OTP status → FAILED

**Решение по передаче phone:** Core API передаёт зашифрованный phone напрямую в задачу (не phone_hash). SMS Worker расшифровывает перед отправкой. Это избегает дополнительного DB-запроса в worker и соблюдает PII-изоляцию (phone не в plaintext в Celery broker).

**Альтернатива:** SMS Worker делает DB lookup по phone_hash. Отвергнута — worker не ДОЛЖЕН иметь прямого доступа к DB по архитектуре (§4.3: "Своя база: НЕТ").

### D7: User creation — при первом OTP-запросе (PENDING_VERIFICATION)

**Решение:** По §6.5, при первом `POST /auth/send-code` на новый номер:
1. Создать `users` (status=PENDING_VERIFICATION) + `user_profiles` (phone encrypted)
2. НЕ создавать `loyalty_accounts` — только при ACTIVE (§6.5: "Создаётся loyalty_accounts при верификации")
3. При успешной верификации: users.status → ACTIVE, создать loyalty_accounts (balance=0)

Повторный запрос на существующий PENDING_VERIFICATION user — просто отправить новый OTP (с rate-limit).

### D8: API Design

**Эндпоинты:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/send-code` | No | Отправить OTP. Body: `{phone: "+7..."}` |
| POST | `/api/v1/auth/verify-code` | No | Верифицировать OTP. Body: `{phone: "+7...", code: "123456"}` |
| POST | `/api/v1/auth/refresh` | No | Обновить токены. Body: `{refresh_token: "..."}` |
| POST | `/api/v1/auth/logout` | Yes | Завершить сессию. Удалить refresh из Redis |

## State Machine References

**OTP Lifecycle (§6.4):** Все 5 состояний и переходы реализуются через Redis Lua-скрипт. Forbidden transitions (CREATED → VERIFIED, CREATED → EXPIRED) MUST быть явно заблокированы (INV-016).

**User Account Lifecycle (§6.5):** В scope этого change: PENDING_VERIFICATION → ACTIVE. Остальные transitions (ACTIVE → BLOCKED, etc.) — в последующих changes.

## 152-ФЗ Compliance

Per INV-013:
- `users.phone_hash` — SHA-256, non-reversible, для lookup
- `user_profiles.phone` — AES-256-GCM encrypted, ключ в env var
- `user_profiles` — отдельная таблица, 1:1 с users, изолирована от orders
- При будущем удалении аккаунта (ACTIVE → DELETED): PII из user_profiles удаляются, orders сохраняются с анонимизированным user_id
- ENCRYPTION_KEY MUST быть в env var (INV-015)

## Migration Strategy

**Forward migration (0002_auth_tables.py):**
1. Создать ENUM types: `user_status` (pending_verification, active, blocked, deleted)
2. Создать таблицу `users` (id UUID PK, phone_hash VARCHAR UNIQUE, status user_status, created_at, deleted_at)
3. Создать таблицу `user_profiles` (user_id UUID FK→users PK, phone BYTEA, display_name VARCHAR NULL, preferred_language VARCHAR DEFAULT 'ru')
4. Создать таблицу `loyalty_accounts` (user_id UUID FK→users PK, balance INTEGER DEFAULT 0, created_at)
5. Создать индекс `ix_users_phone_hash` на `users.phone_hash`

**Rollback:** Drop tables in reverse order, drop ENUM types.

**Data backfill:** Не требуется — greenfield, таблицы пустые.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| SMS.ru недоступен → пользователи не могут войти | Retry 3x с backoff (§7.8). Graceful error message. В будущем: fallback на SMSC |
| Redis restart → потеря активных OTP и сессий | Приемлемо — OTP TTL 5 мин, пользователь просто запрашивает новый. Refresh tokens тоже re-issuable через re-auth |
| ENCRYPTION_KEY compromise → утечка phone numbers | Key rotation mechanism — out of scope (MVP), но структура (per-record nonce) позволяет добавить key versioning |
| Fixed-window rate limiting → burst на границе окна | Приемлемо для текущих лимитов (1/мин). Sliding window можно добавить позже если станет проблемой |

## Open Questions

1. **SMS content локализация:** PDD указывает "Код подтверждения: {code}. Aura Coffee" (§8.2). Нужен ли EN-вариант для англоязычных пользователей? → Предлагаю: только RU для SMS (телефон = РФ номер), i18n для SMS — overkill на MVP.
2. **OTP resend UX:** При повторном запросе на тот же номер с активным OTP — создавать новый OTP или возвращать оставшийся TTL? → Предлагаю: создавать новый (invalidate старый), с проверкой rate-limit.
