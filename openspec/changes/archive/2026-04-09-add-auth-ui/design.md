## Affected Modules

`[web-customer]`

## Context

Customer SPA (`web/customer/`) — React 19 + TypeScript, Vite, Tailwind CSS, shadcn/ui, react-i18next, React Router. Текущее состояние: scaffold с placeholder-страницами (Home, Cart, Checkout, Orders, Profile, 404). Роутинг настроен, i18n работает (RU/EN).

Backend auth API (`sms-otp-auth`) разрабатывается параллельно. Эндпоинты: `POST /api/v1/auth/send-code`, `verify-code`, `refresh`, `logout`. На время разработки фронтенда используются моки API — замена на реальные вызовы будет произведена отдельно по команде.

## Goals / Non-Goals

**Goals:**
- Реализовать полный UI flow SMS OTP авторизации (§6.4): ввод телефона → ввод кода → сессия
- Реализовать управление токенами (access + refresh JWT) на клиенте
- Реализовать защиту роутов: неаутентифицированные пользователи перенаправляются на `/login`
- Использовать моки вместо реального API на время параллельной разработки backend

**Non-Goals:**
- Backend auth API (покрывается `sms-otp-auth` change)
- Авторизация персонала (admin/barista/courier)
- Личный кабинет (профиль, адреса) — отдельный change
- Auto-generated API client из OpenAPI spec — будет настроен при интеграции

## Decisions

### D1: Мокированный API-клиент с заменяемой реализацией

**Решение:** Auth API client реализован как модуль `src/api/auth.ts` с интерфейсом, за которым стоит мок-реализация (`src/api/mocks/auth.ts`). Мок имитирует задержки и возвращает предсказуемые ответы. При переключении на реальный API — заменяется импорт в `auth.ts`.

**Альтернатива:** MSW (Mock Service Worker). Отвергнута — добавляет dev-зависимость и усложняет setup для одного модуля. Inline-мок проще и достаточен.

### D2: Хранение токенов — in-memory + localStorage для refresh

**Решение:**
- Access token: хранится in-memory (переменная в auth module). НЕ в localStorage — минимизация attack surface при XSS.
- Refresh token: localStorage. При загрузке страницы — silent refresh через `/auth/refresh`.

**Альтернатива:** Оба токена в localStorage. Отвергнута — access token в localStorage доступен любому JS-коду на странице, увеличивает риск при XSS.

**Альтернатива:** httpOnly cookies. Отвергнута — требует backend-изменений (cookie-based auth не в scope `sms-otp-auth`), усложняет CORS.

### D3: AuthContext + useAuth hook

**Решение:** React Context предоставляет: `{ user, isAuthenticated, isLoading, login, verifyCode, logout }`. `useAuth()` hook для доступа из компонентов. `AuthProvider` оборачивает всё приложение, при mount пытается silent refresh.

### D4: ProtectedRoute — redirect на /login

**Решение:** Компонент `ProtectedRoute` проверяет `isAuthenticated` из AuthContext. Если нет — `<Navigate to="/login" />` с сохранением `returnUrl` в state. После успешного логина — redirect на сохранённый URL.

### D5: OTP ввод — отдельные input-поля (6 цифр)

**Решение:** Компонент `OTPInput` — 6 отдельных `<input>` полей для каждой цифры. Auto-focus на следующее поле при вводе, backspace возвращает на предыдущее. Auto-submit при заполнении всех 6.

**Альтернатива:** Единое текстовое поле с маской. Отвергнута — хуже UX на мобильных устройствах, стандартный паттерн для OTP — раздельные поля.

### D6: Таймер повторной отправки — 60 секунд

**Решение:** После отправки кода — обратный отсчёт 60с (§6.4: rate-limit 1/мин). Кнопка "Отправить повторно" неактивна до истечения таймера. Таймер хранится в компонентном state.

### D7: Phone input — маска +7

**Решение:** Input с фиксированным префиксом `+7`, маска `(XXX) XXX-XX-XX`. Валидация: ровно 10 цифр после +7. Нормализация в E.164 (`+7XXXXXXXXXX`) перед отправкой. Реализация без дополнительных зависимостей — controlled input с обработкой onChange.

### D8: Мок-поведение

**Решение:** Мок SHALL реализовать следующие сценарии:
- `send-code`: любой валидный номер → успех, задержка 500ms
- `verify-code`: код `000000` → успех (возвращает mock JWT), любой другой → ошибка "Неверный код"
- `refresh`: если есть refresh token → новая пара токенов
- `logout`: всегда успех

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| In-memory access token теряется при refresh страницы | Silent refresh при mount через refresh token из localStorage |
| Мок-реализация расходится с реальным API | Мок следует контракту из `sms-otp-auth` design.md (§D8). При интеграции — сверка с OpenAPI spec |
| XSS может украсть refresh token из localStorage | Приемлемо для MVP. CSP headers + sanitization снижают риск. httpOnly cookies — future improvement |

## Open Questions

1. **Нужен ли экран "Успешная регистрация"?** При первом входе backend создаёт аккаунт автоматически. Предлагаю: нет отдельного экрана, просто redirect на главную с кратким toast "Добро пожаловать".
