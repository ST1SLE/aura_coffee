# Owner Decision Packet Before Public Launch

This packet collects the non-code decisions that currently block Aura Coffee
from moving beyond closed staging. It is safe to share with the owner or
provider-account operator because it asks for decisions and access status, not
secret values.

Do not paste API keys, passwords, recovery codes, bank details, or customer
phone numbers into this file or chat. Record only whether the owner/provider
side is ready and who owns the next action.

## Current Closed-Staging Facts

- Domain: `staging.aura-coffee-bakery.ru` points to VPS `212.8.226.214`.
- Public production domain `aura-coffee-bakery.ru` stays parked until launch
  gates pass.
- Active staging release: `3c8bacc-codex-no-query-logs-20260511T150202Z`.
- Provider modes are intentionally closed-staging only:
  `SMS_BACKEND=log` and `YUKASSA_BACKEND=fake`.
- Yandex Suggest/Geocoder works through the Aura Core API proxy on closed
  staging, but delivery launch still needs license/storage and quota decisions.
- Backups, recurring ops checks, security headers, scanner-path denies, SSH
  hardening, and no-query logs are in place.
- Remaining ops warning: provider dashboard alerts are manual for SMS.ru
  balance, Yandex quota/billing, and YuKassa failures.

## Immediate Owner Decisions

| Area | Decision Needed | Launch Impact | Codex Action After Answer |
|------|-----------------|---------------|---------------------------|
| SMS.ru | Confirm controlled test phone availability, balance, daily spend/volume limit, and whether shared `SMS.RU` code sender is acceptable for launch. | Blocks real OTP login smoke. | Switch staging to `SMS_BACKEND=smsru`, run controlled OTP smoke, inspect `BLOCK_SMSRU_CALL` and redaction, then roll forward or back. |
| YuKassa | Confirm owner/business account, test shop access, webhook setup owner, 54-FZ receipt path, and refund policy owner. | Blocks real payment/webhook/refund smoke. | Configure test credentials on staging, run test payment, webhook, duplicate, invalid-source, and refund drills. |
| Yandex Maps | Decide whether launch includes delivery, pickup-only first, or delivery deferred; confirm storage/license answer for persisting Yandex-derived address/coordinate data. | Blocks public delivery launch. | Run delivery checkout smoke if delivery is approved, or configure launch plan as pickup-first if not. |
| Legal/152-FZ | Assign owner for privacy policy, personal-data consent, public offer or terms, refund/cancellation policy, and Roskomnadzor/operator duties. | Blocks public collection of phone/name/address and online prepayment. | Publish approved texts and run final public-page/legal-link checks. |
| Menu/media | Approve final RU/EN names, prices, size labels, item availability, media quality, and cacao/matcha alternative-milk pricing. | Blocks final menu import and public browsing confidence. | Validate/import final catalog and run customer menu/media smoke. |
| Staff operations | Confirm production staff accounts, role ownership, operating hours, pickup/delivery procedures, support contact, and refund escalation path. | Blocks controlled live cutover and staff readiness. | Run private end-to-end staff flow and one-order drill. |
| Provider alerts | Confirm dashboard alert owners for SMS.ru balance, Yandex quota/billing, and YuKassa failed payments/webhooks. | Blocks monitoring gate before launch. | Record alert evidence and clear the remaining ops-health manual warning from the launch checklist. |

## Questions To Send To The Owner

### Paste-Ready Owner Message

```text
Привет! Сайт Aura Coffee сейчас готов как закрытый staging: домен и VPS
работают, HTTPS включен, база/Redis закрыты от интернета, бэкапы и проверки
настроены, базовая защита и логи без PII включены.

Публичный запуск сейчас блокируют только бизнес/provider-решения. Не присылай
секреты, API-ключи, пароли, коды восстановления, банковские данные или телефоны
клиентов в чат. Нужны только решения, владельцы задач и статус доступа.

Ответь, пожалуйста, по пунктам:

1. SMS.ru
- Какой телефон используем для контрольного OTP-теста и когда он будет доступен?
- Ок ли запускаться с обычным сервисным отправителем SMS.RU, если брендированный
  отправитель требует договора ИП/юрлица и ежемесячных платежей?
- Какой баланс и дневной лимит расходов/сообщений ставим перед первым тестом?
- Кто будет следить за балансом и ошибками доставки в SMS.ru?

2. YuKassa и чеки
- Кто владеет бизнес-аккаунтом YuKassa и recovery email?
- Доступен ли test shop?
- Какой путь по 54-ФЗ утверждаем: чеки от YuKassa или отдельная онлайн-касса?
- Какие правила возврата/отмены онлайн-заказов должны соблюдать сотрудники?
- Кто проверяет чек/фискальный статус после контрольной живой оплаты?
- Кто отвечает за алерты по webhook/payment failures в YuKassa?

3. Яндекс Карты и доставка
- Запускаемся сразу с доставкой или сначала pickup-only?
- Есть ли подтверждение от Яндекса, можно ли нам хранить адрес/координаты/
  точность геокодера для проверки зоны доставки?
- Если нужна платная/advanced-лицензия, одобряем стоимость или откладываем
  доставку?
- Настроены ли production restrictions, квоты, billing threshold и алерты?

4. Юридическое и персональные данные
- Кто владелец 152-ФЗ/privacy/Roskomnadzor решений?
- Утверждены ли privacy policy, согласие на персональные данные, оферта/terms,
  refund/cancellation policy и реквизиты/контакты бизнеса для сайта?
- Ок ли текущий hosting/location setup для требований локализации данных?
- Будут ли на запуске analytics/pixels/third-party tracking? Если да, кто
  утверждает notice/consent текст?

5. Меню, медиа и операции
- Утверждены ли русские и английские названия категорий/товаров?
- Утверждены ли размеры, объемы, цены и доступность?
- Ок ли текущие глобальные цены на альтернативное молоко для cacao/matcha,
  или каталог нужно менять до запуска?
- Утверждены ли все фото/poster/video для публичного показа?
- Какие часы работы, правила pickup/delivery, зона доставки и support contact?
- Кому нужны production-доступы admin/barista/courier?

После ответов мы сможем безопасно выполнить следующий технический шаг:
реальный SMS.ru OTP smoke, затем YuKassa test-shop payment/webhook/refund drills,
затем delivery/menu/legal/staff full private smoke.
```

### 1. SMS.ru

1. Which phone will be used for the controlled OTP smoke, and when will the
   phone be available?
2. Is the owner comfortable launching with SMS.ru service-code behavior from
   the shared `SMS.RU` sender if branded sender registration is expensive?
3. What balance and daily spend or volume limit should be active before the
   first real OTP test?
4. Who monitors low balance or delivery failures in the SMS.ru dashboard?

### 2. YuKassa And Receipts

1. Who owns the YuKassa business account and recovery email?
2. Is a YuKassa test shop available now?
3. Which 54-FZ receipt route is approved: YuKassa checks or a separate online
   cash register/cloud cash register?
4. What refund and cancellation rules should staff follow for online orders?
5. Who verifies receipt/fiscal status after the controlled live payment?
6. Who owns YuKassa webhook/failure alerts?

### 3. Yandex Maps And Delivery

1. Should public launch include delivery, or should Aura launch pickup-only
   first?
2. Has Yandex support/account management confirmed whether Aura may persist
   geocoder-derived address text, coordinates, and precision for delivery-zone
   validation?
3. If a paid/advanced license is required, is the owner approving that cost or
   deferring delivery?
4. Are production key restrictions, quota limits, billing threshold, and usage
   alerts configured in the Yandex dashboard?

### 4. Legal And Personal Data

This is not legal advice; the owner/accountant/lawyer must approve the final
position before public traffic.

1. Who owns 152-FZ/privacy compliance and Roskomnadzor/operator notification
   decisions?
2. Are privacy policy, personal-data consent, public offer or ordering terms,
   refund/cancellation policy, and business contact details approved for the
   website?
3. Is the hosting/location setup acceptable for Russian personal-data
   localization obligations?
4. Will analytics, pixels, or third-party tracking be added at launch? If yes,
   who approves the notice/consent wording?

### 5. Menu, Media, And Shop Operations

1. Are all Russian and English item/category names approved?
2. Are size labels, volumes, prices, and availability approved?
3. Are cacao/matcha alternative-milk price deltas acceptable with the current
   global modifier prices, or should the catalog change before launch?
4. Are all product posters/videos acceptable for public display?
5. What are launch operating hours, pickup expectations, delivery zone rules,
   and customer support contact?
6. Which staff members need production admin/barista/courier access?

## Ready-To-Run Sequence After Owner Answers

1. SMS.ru controlled OTP smoke.
2. YuKassa test-shop payment, webhook, duplicate, invalid-source, and refund
   drills.
3. Yandex delivery checkout smoke, or explicit pickup-first launch adjustment.
4. Final menu/media validation and import.
5. Full private end-to-end smoke with real SMS and YuKassa test payments.
6. Controlled live cutover with one owner-approved real pickup order.

Use `docs/shipping-website/07-smsru-controlled-otp-smoke.md` for the SMS.ru
operator checklist and evidence log when step 1 is unblocked.
Use `docs/shipping-website/08-yukassa-test-payment-smoke.md` for the YuKassa
test-shop payment/refund/rejection checklist when step 2 is unblocked.
Use `docs/shipping-website/09-yandex-delivery-decision-smoke.md` for the Yandex
delivery/pickup-first decision and delivery checkout smoke when step 3 is
unblocked.

## Stop Conditions

Do not open public traffic if any of these are still true:

- `SMS_BACKEND=log` or `YUKASSA_BACKEND=fake` is active.
- YuKassa test-shop payment and webhook path has not passed.
- SMS.ru controlled OTP has not passed with redaction inspection.
- Delivery is enabled without an approved Yandex storage/license position.
- Legal/privacy/offer/refund/consent text is missing or unapproved.
- Final menu/prices/media are not owner-approved.
- Provider dashboard alerts have no owner.
