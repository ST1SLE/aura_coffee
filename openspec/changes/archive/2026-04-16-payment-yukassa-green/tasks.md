## 1. Runtime dependencies and packaging

- [x] 1.1 [payment-worker] PREREQ: promote `httpx>=0.27,<1.0`, `fastapi>=0.111,<1.0`, `sqlalchemy>=2.0,<2.1` from `[project.optional-dependencies].dev` to `[project.dependencies]` in `services/payment-worker/pyproject.toml`. Add `uvicorn[standard]>=0.30,<1.0` to runtime deps. Leave `respx`, `fakeredis`, `pytest-asyncio`, `ruff`, `pytest` under `[dev]`.

## 2. Settings

- [x] 2.1 [payment-worker] GREEN: rewrite `services/payment-worker/src/payment_worker/settings.py` so `Settings(BaseSettings)` exposes: `redis_url`, `database_url`, `yukassa_shop_id`, `yukassa_secret_key`, `yukassa_webhook_ips: list[str]` (use a pydantic field validator to split on "," and `.strip()` each entry), `yukassa_base_url: str = "https://api.yookassa.ru/v3"`. Env prefix stays empty (env var names = UPPER_SNAKE of field name).
- [x] 2.2 [payment-worker] VERIFY: `pytest services/payment-worker/tests/test_settings.py -v` — all 3 tests PASS.

## 3. YuKassa HTTP client

- [x] 3.1 [payment-worker] GREEN: create `services/payment-worker/src/payment_worker/yukassa_client.py` with:
  - constant `DEFAULT_BASE_URL = "https://api.yookassa.ru/v3"`
  - `_format_amount(kopecks: int) -> str` → `f"{kopecks // 100}.{kopecks % 100:02d}"`
  - `class YukassaClient` with `__init__(shop_id, secret_key, base_url=DEFAULT_BASE_URL, timeout=None)`: builds `httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)` if not provided, stores it as `self.timeout`, and creates `self._client = httpx.Client(auth=(shop_id, secret_key), timeout=self.timeout)`
  - `create_payment(amount_kopecks, idempotency_key, return_url, description) -> dict`: POST `{base_url}/payments` with header `Idempotency-Key` and JSON `{"amount": {"value": _format_amount(...), "currency": "RUB"}, "confirmation": {"type": "redirect", "return_url": ...}, "capture": True, "description": ...}`; returns `{"payment_id": resp["id"], "confirmation_url": resp["confirmation"]["confirmation_url"], "status": resp["status"]}`.
  - `get_payment(payment_id) -> dict`: GET `{base_url}/payments/{payment_id}`; no idempotency header; returns parsed JSON.
  - `create_refund(payment_id, amount_kopecks, idempotency_key) -> dict`: POST `{base_url}/refunds` with header `Idempotency-Key` and JSON `{"payment_id": payment_id, "amount": {"value": _format_amount(...), "currency": "RUB"}}`; returns parsed JSON.
  - Every method calls `response.raise_for_status()` before returning.
- [x] 3.2 [payment-worker] VERIFY: `pytest services/payment-worker/tests/test_yukassa_client.py -v` — all 9 tests PASS.

## 4. DB and Redis accessors

- [x] 4.1 [payment-worker] GREEN: create `services/payment-worker/src/payment_worker/db.py` with `get_engine()` (lazy `create_engine(settings.database_url, future=True)`; cache on a module global after first call) and `session_scope()` context manager yielding a `Session(bind=get_engine(), expire_on_commit=False)` with `commit()` on normal exit and `rollback()` on exception.
- [x] 4.2 [payment-worker] GREEN: create `services/payment-worker/src/payment_worker/redis_client.py` with `get_redis()` (lazy `redis.Redis.from_url(settings.redis_url, decode_responses=False)`).

## 5. Celery tasks

- [x] 5.1 [payment-worker] GREEN: rewrite `services/payment-worker/src/payment_worker/tasks.py`. It MUST:
  - `from payment_worker.yukassa_client import YukassaClient` at module top (so tests can `patch("payment_worker.tasks.YukassaClient", create=True)` — but even without `create=True` the symbol exists).
  - `from payment_worker.db import get_engine, session_scope`.
  - Keep the existing `health_check` task.
  - Define `@celery_app.task(bind=True, name="payment_worker.tasks.create_payment", autoretry_for=(httpx.RequestError,), retry_backoff=True, retry_backoff_max=60, max_retries=3) def create_payment(self, order_id: str, amount_kopecks: int, idempotency_key: str)`. Body: fetch `Order` + `Payment` by `order_id` (first Payment row for that order, or by explicit `payment_id` looked up from Order); instantiate `YukassaClient(settings.yukassa_shop_id, settings.yukassa_secret_key, settings.yukassa_base_url)`; call `create_payment`; on success update Payment in a new session; on `httpx.RequestError` let Celery auto-retry; when `self.request.retries >= self.max_retries` wrap the final raise with `_fail_payment_and_cancel_order(order_id, payment_id)` then re-raise.
  - Define `_fail_payment_and_cancel_order(order_id: str, payment_id: str)` as a module-level function. Single `session_scope()`: load Payment + Order; set `Payment.status = PaymentStatus.PAYMENT_FAILED`; set `Order.status = OrderStatus.CANCELLED`; if `Order.points_used > 0`, compute current `balance_after` by summing prior `LoyaltyTransaction.amount` for that user (ordered by `created_at`, take the last row's `balance_after`; if no rows treat as 0), insert `LoyaltyTransaction(user_id=order.user_id, order_id=order.id, type=LoyaltyTransactionType.REVERSAL, amount=order.points_used, balance_after=last_balance + order.points_used, description="reversed: payment failed")`; if `order.promocode_id is not None` call `_decrement_promocode(session, order.promocode_id)`.
  - Define `_decrement_promocode(session, promocode_id)` — `UPDATE Promocode SET current_uses = current_uses - 1 WHERE id = :id AND current_uses > 0` (or ORM equivalent: `promo = session.get(Promocode, promocode_id); if promo.current_uses > 0: promo.current_uses -= 1`).
  - Define `@celery_app.task(bind=True, name="payment_worker.tasks.initiate_refund", max_retries=0) def initiate_refund(self, payment_id: str, amount_kopecks: int)`. Body: inside a try/except catching `Exception`: build client, call `create_refund`, then in `session_scope()` set `Payment.status = REFUND_PENDING`. On exception: log and return.
- [x] 5.2 [payment-worker] VERIFY: `pytest services/payment-worker/tests/test_tasks.py -v` — all 6 tests PASS. If they don't, DO NOT edit test files — fix the implementation.

## 6. Webhook FastAPI app

- [x] 6.1 [payment-worker] GREEN: create `services/payment-worker/src/payment_worker/webhook.py` with:
  - `app = FastAPI()`.
  - `from payment_worker.db import get_engine, session_scope` (both modules must expose `get_engine` so tests can patch).
  - `from payment_worker.redis_client import get_redis`.
  - Helper `_client_ip(request) -> str`: inspect `request.headers.get("X-Forwarded-For")` first (take the first hop, trimmed), else `request.client.host`.
  - Helper `_is_whitelisted(ip, whitelist: list[str]) -> bool`: for each entry, if `/` in entry → `ipaddress.ip_address(ip) in ipaddress.ip_network(entry, strict=False)`; else exact string match.
  - Idempotency helpers `is_event_processed(redis, event_id) -> bool` and `mark_event_processed(redis, event_id) -> None` (`EXISTS` / `SET EX 86400`).
  - Module-level `dispatch_event(session, redis, event: str, obj: dict) -> None` — dispatches by `event` string (see below). Each branch mutates via the given `session` (caller owns the transaction).
  - Endpoint `@app.post("/webhooks/yukassa") async def yukassa_webhook(request: Request)`:
    1. IP check → 403 on miss (uses `JSONResponse(status_code=403)`).
    2. Read `X-Event-Id` → if empty, fall back to `hashlib.sha256(body).hexdigest()`. Check idempotency store → 200 on hit.
    3. Open `session_scope()`; call `dispatch_event(session, redis, body["event"], body["object"])`; on successful commit call `mark_event_processed(redis, event_id)`.
    4. On exception: raise (FastAPI default converts to 500, and under TestClient re-raises the original — matching the RED test).
    5. Return `{"ok": True}` on success.
  - Event handlers inside `dispatch_event`:
    - `"payment.succeeded"`: fetch Payment by `yukassa_payment_id = obj["id"]`; load its Order; guard `Payment.status == AWAITING_CONFIRMATION` (if already SUCCEEDED, no-op); set Payment/Order to SUCCEEDED/PAID; compute redemption: find the latest RESERVATION row for this order, compute new `balance_after`, insert `LoyaltyTransaction(user_id, order_id, type=REDEMPTION, amount=-abs(reservation.amount), balance_after=latest_balance + (-abs(...)))` — NB: the test only asserts existence of at least one REDEMPTION row for the order, not the exact balance math; keep this simple and correct; drop Redis cart key `cart:{user_id}` AFTER commit (or within the same session — behavior is idempotent); insert two notifications (SMS + IN_APP) with `message_ru="Заказ оплачен. Номер заказа: ..."`.
    - `"payment.canceled"`: fetch Payment + Order; inline the same body as `_fail_payment_and_cancel_order` (Payment→PAYMENT_FAILED, Order→CANCELLED, REVERSAL insert, promocode decrement); insert one `Notification(channel=IN_APP, message_ru="Платёж не прошёл. ...")`.
    - `"refund.succeeded"`: fetch Payment by `yukassa_payment_id = obj["payment_id"]`; set `Payment.status = REFUNDED`.
    - `"refund.canceled"`: fetch Payment; set `Payment.status = REFUND_FAILED`; insert `Notification(order_id=payment.order_id, channel=IN_APP, message_ru="Возврат не прошёл — требуется ручное вмешательство", user_id=None)` (or with the order's user_id — only row existence is asserted).
    - any other event: log and return (no-op).
  - Put cart deletion and `mark_event_processed` AFTER the session commits, so they cannot partially apply if the DB rolls back. The RED test `test_processing_exception_surfaces_as_500` verifies that `yukassa:event:{event_id}` is absent when the dispatcher raises.
- [x] 6.2 [payment-worker] VERIFY: `pytest services/payment-worker/tests/test_webhook.py -v` — all 8 tests PASS.

## 7. Celery app wiring preserved

- [x] 7.1 [payment-worker] REFACTOR: ensure `services/payment-worker/src/payment_worker/main.py` still creates the `celery_app` and that tasks (including new ones) are discovered. The existing `autodiscover_tasks(["payment_worker"])` plus task names `payment_worker.tasks.create_payment`, `payment_worker.tasks.initiate_refund` are sufficient — no additional wiring needed. `health_check` remains.

## 8. Full suite verification

- [x] 8.1 [payment-worker] VERIFY: `pytest services/payment-worker/tests/ -v` — all 26 tests PASS, no regressions, no test-file edits.
- [x] 8.2 [payment-worker] VERIFY: `ruff check services/payment-worker/src services/payment-worker/tests` — no new lint errors introduced by GREEN code (fix trivial issues if surfaced).
