## Why

Все мутации состояния требуют серверной аутентификации (INV-002, INV-010). Backend auth API (`sms-otp-auth` change) разрабатывается параллельно — фронтенду нужны экраны логина, управление токенами и защита роутов, чтобы пользователь мог пройти SMS OTP flow и получить доступ к приложению. Без auth-ui невозможны: оформление заказа, оплата, профиль, баллы лояльности.

## What Changes

- Экран ввода номера телефона: маска +7, валидация формата, кнопка "Получить код"
- Экран ввода OTP-кода: 6-значный ввод, таймер обратного отсчёта (60с до повторной отправки), обработка ошибок (неверный код, истёкший, слишком много попыток)
- API-клиент для auth-эндпоинтов: `POST /api/v1/auth/send-code`, `verify-code`, `refresh`, `logout`
- Управление токенами: хранение access/refresh в памяти и/или localStorage, автоматический refresh при 401, attach access token к каждому запросу
- Auth context (React Context): текущий пользователь, состояние аутентификации, logout
- Защита роутов: перенаправление неаутентифицированных пользователей на экран логина
- i18n: ключи для auth-экранов на RU и EN

## Non-Goals

- Backend auth API (OTP lifecycle, JWT generation, rate-limiting, SMS worker) — отдельный change `sms-otp-auth`
- Авторизация персонала (admin/barista/courier login/password) — отдельный change
- Личный кабинет: профиль, смена языка, управление адресами — отдельный change (Phase 1, §7.1 п.3)
- RBAC middleware и role-based UI filtering — будет при реализации admin panel
- Восстановление аккаунта / смена номера телефона

## MVP Phase

**Phase 1: Auth & User Profile** (§7.1) — данный change покрывает frontend-часть пунктов 1 и 2 (SMS OTP авторизация + регистрация при первом входе).

## Capabilities

### New Capabilities

- `auth-screens`: UI-компоненты для SMS OTP login flow — экран ввода телефона, экран ввода кода, обработка состояний (loading, error, success)
- `auth-api-client`: HTTP-клиент для взаимодействия с auth API (send-code, verify-code, refresh, logout), interceptor для auto-refresh
- `auth-state`: React Context для управления аутентификацией — текущий пользователь, токены, protected routes

### Modified Capabilities

- `frontend-routing`: Добавление auth-роутов (`/login`, `/login/verify`) и ProtectedRoute wrapper для существующих роутов

## Impact

- **web-customer** (`web/customer/`): новые страницы, компоненты, хуки, API-клиент, auth context, обновление роутинга
- **i18n**: новые ключи переводов для auth-экранов (RU, EN)
- **Зависимости**: возможно добавление HTTP-клиента (fetch wrapper или axios) если отсутствует
- **Роутинг**: модификация `App.tsx` — добавление auth-роутов и protected route logic
