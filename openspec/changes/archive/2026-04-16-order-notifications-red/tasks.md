## 1. Test module scaffolding

- [x] 1.1 [core-api] PREREQ: create empty test module `services/core-api/tests/test_notification_service.py` with a top-of-file docstring describing the RED contract (pins `core_api.services.notification.send_order_notification` per PDD §6.1 / §7.8 / §8.2 / INV-013 / INV-016), imports `uuid`, `pytest`, `from unittest.mock import patch, MagicMock`, and (at module top) `from shared.enums import OrderStatus, OrderType, NotificationChannel, NotificationStatus, NotificationType`. Do NOT import the target service at module level — imports for it happen inside test bodies.
- [x] 1.2 [core-api] PREREQ: create empty test module `services/core-api/tests/test_notification_messages.py` with a docstring explaining it freezes the PDD §6.1 text matrix, imports `pytest` and `from shared.enums import OrderStatus, OrderType`. Target module is imported inside test bodies only.
- [x] 1.3 [sms-worker] PREREQ: create empty test module `services/sms-worker/tests/test_notification_task.py` with a docstring describing the RED contract (pins `sms_worker.tasks.notification.send_order_notification_sms` per PDD §7.8 / §8.2 / INV-013), imports `uuid`, `pytest`, `from unittest.mock import MagicMock, patch`, `from cryptography.hazmat.primitives.ciphers.aead import AESGCM`, and the Celery app fixture pattern already used in `test_otp_task.py`. Target task is imported inside test bodies.

## 2. RED: core-api test fixtures and helpers (in test_notification_service.py)

- [x] 2.1 [core-api] RED: add fixture `def make_order(db_session, user)` that inserts a minimally-valid `Order` row (new UUID, `type=PICKUP`, `status=CREATED`, kopeck fields set to 0, `subtotal=total=1000`) and returns the persisted instance. Test `test_make_order_fixture_smoke` asserts the fixture returns an `Order` with a UUID `id` and the expected `type`. MUST fail at collection because `Order` import fails OR fixture helper is missing until GREEN.
- [x] 2.2 [core-api] RED: add fixture `def encrypted_phone_hex_for(user_profile)` that returns the `phone_encrypted` hex stored on `user_profiles`. Test `test_fixture_returns_hex_string` asserts the return matches `^[0-9a-f]+$` and length > 24. MUST fail until the matching service import works in later tests.

## 3. RED: core-api IN_APP row tests (test_notification_service.py)

- [x] 3.1 [core-api] RED: add `test_paid_writes_in_app_row_status_sent` — imports `send_order_notification` inside the body, calls it with `new_status=OrderStatus.PAID`, asserts exactly one row exists in `notifications` with `channel = IN_APP`, `type = ORDER_STATUS_CHANGE`, `status = SENT`, populated `message_ru` and `message_en`, and FKs matching user/order. MUST fail with `ImportError` in RED.
- [x] 3.2 [core-api] RED: add `test_in_app_row_written_for_every_status_with_notification` — parametrize over all 9 §6.1 triples; for each triple assert an IN_APP row is written (same columns as 3.1). MUST fail in RED.
- [x] 3.3 [core-api] RED: add `test_in_app_row_text_matches_preferred_language_selection` — seed one user with `preferred_language="ru"` and a second with `preferred_language="en"`; for each, call `send_order_notification(new_status=PAID)`. Assert that both `message_ru` and `message_en` are populated (both columns are written regardless of preference), AND assert that a helper `resolve_display_text(notification, preferred_language)` returns the matching field. MUST fail in RED.

## 4. RED: core-api SMS row + dispatch tests (test_notification_service.py)

- [x] 4.1 [core-api] RED: add `test_paid_writes_sms_row_status_pending` — calls service with `new_status=PAID`, asserts a second row exists with `channel = SMS`, `status = PENDING`, populated `message_ru`/`message_en`. MUST fail in RED.
- [x] 4.2 [core-api] RED: add `test_in_delivery_does_not_write_sms_row` — calls with `new_status=IN_DELIVERY`, `order.type=DELIVERY`, asserts only IN_APP row exists. MUST fail in RED.
- [x] 4.3 [core-api] RED: add `test_completed_pickup_does_not_write_sms_row` — calls with `new_status=COMPLETED`, `order.type=PICKUP`, asserts only IN_APP row exists. MUST fail in RED.
- [x] 4.4 [core-api] RED: add `test_sms_required_cases_enqueue_celery_task` — parametrize the 7 SMS-required cases. Patch `core_api.services.notification.send_order_notification_sms` (or an equivalent dispatcher attribute) with `MagicMock`; call service; assert the mock was called exactly once with kwargs/positional `(notification_id, encrypted_phone_hex, message)` where `notification_id` is a UUID equal to the SMS row's id, `encrypted_phone_hex` matches the profile's stored hex, and `message` equals the expected SMS body from the matrix. MUST fail in RED.
- [x] 4.5 [core-api] RED: add `test_in_app_only_cases_do_not_enqueue_task` — parametrize the 2 in-app-only cases; assert the mock dispatcher is not called. MUST fail in RED.
- [x] 4.6 [core-api] RED: add `test_celery_task_is_dispatched_by_registered_name` — asserts that the dispatcher the service uses points at a Celery task whose `.name == "sms_worker.send_order_notification_sms"`. MUST fail in RED.
- [x] 4.7 [core-api] RED: add `test_plaintext_phone_never_passed_to_task` (INV-013) — set `user_profile.phone_encrypted` to a real AESGCM ciphertext of `+79991234567`; invoke service; assert `mock_dispatcher.call_args` second positional != `"+79991234567"` and matches `^[0-9a-f]+$`. MUST fail in RED.
- [x] 4.8 [core-api] RED: add `test_sms_row_committed_before_dispatch` — wrap `mock_dispatcher.side_effect` to, at call time, re-query the DB and assert the SMS row's id exists and `status == PENDING` (i.e. the commit happened before the task was enqueued). MUST fail in RED.

## 5. RED: core-api short_id and cancellation semantics (test_notification_service.py)

- [x] 5.1 [core-api] RED: add `test_short_id_is_first_8_hex_chars_of_uuid` — fabricate an order with `id = UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")`; call service; assert `"c0ffee11"` appears as a substring in both `message_ru` and `message_en` of the IN_APP row AND in the message arg passed to the dispatcher. MUST fail in RED.
- [x] 5.2 [core-api] RED: add `test_cancelled_by_customer_uses_refund_wording` — calls with `new_status=CANCELLED, cancelled_by="customer"`; assert `message_ru` equals `f"Заказ №{short_id} отменён, средства возвращены"`. MUST fail in RED.
- [x] 5.3 [core-api] RED: add `test_cancelled_by_admin_uses_coffee_shop_wording` — calls with `new_status=CANCELLED, cancelled_by="admin"`; assert `message_ru` equals `f"Заказ №{short_id} отменён кофейней"`. MUST fail in RED.
- [x] 5.4 [core-api] RED: add `test_cancelled_without_cancelled_by_raises` — calls with `new_status=CANCELLED, cancelled_by=None`; assert the call raises `ValueError`. MUST fail in RED.
- [x] 5.5 [core-api] RED: add `test_unknown_transition_raises` — calls with `new_status=CREATED` (no notification per §6.1); assert `ValueError` and no DB rows written. MUST fail in RED.

## 6. RED: REFACTOR group 3–5 (test_notification_service.py)

- [x] 6.1 [core-api] REFACTOR: extract the common "setup user + order + profile" into a single factory fixture used across tests in `test_notification_service.py` (reduce boilerplate). Verify all tests in the module still FAIL for the same RED reason (ImportError/AssertionError) after the refactor — no test accidentally passes.

## 7. RED: matrix tests (test_notification_messages.py)

- [x] 7.1 [core-api] RED: add module-level `MATRIX` constant listing the 9 tuples `(new_status, order_type, cancelled_by, message_ru, message_en, requires_sms)` with the frozen texts from PDD §6.1 / the proposal. Add `test_matrix_has_nine_cases` asserting `len(MATRIX) == 9`. This test passes trivially but makes the data available; MUST NOT import any target module.
- [x] 7.2 [core-api] RED: add `test_resolve_notification_text_returns_frozen_ru` — parametrize over MATRIX; inside the test body `from core_api.services.notification import resolve_notification_text`; assert it returns a dataclass/tuple whose `message_ru` matches the frozen literal for a fabricated `short_id = "c0ffee11"`. MUST fail with `ImportError` in RED.
- [x] 7.3 [core-api] RED: add `test_resolve_notification_text_returns_frozen_en` — same shape; asserts `message_en` matches the frozen literal. MUST fail in RED.
- [x] 7.4 [core-api] RED: add `test_resolve_notification_text_requires_sms_flag` — parametrize; asserts `requires_sms` flag on the returned value matches the matrix. MUST fail in RED.
- [x] 7.5 [core-api] RED: add `test_sms_body_length_is_within_one_cyrillic_segment` — parametrize over the 7 SMS-required cases; call `build_sms_body(message_ru, short_id="abcdef01")` and assert `len(body) <= 70`; also assert `body.endswith(". Aura Coffee")` and `f"Заказ №abcdef01" in body`. MUST fail with `ImportError` in RED.
- [x] 7.6 [core-api] RED: add `test_sms_body_substitutes_short_id` — calls `build_sms_body("Заказ №{short_id} оплачен", short_id="c0ffee11")`; asserts exact return equals `"Заказ №c0ffee11 оплачен. Заказ №c0ffee11. Aura Coffee"` is FALSE (i.e. there is no double substitution) — more precisely, asserts the returned string equals `"Заказ №c0ffee11 оплачен. Заказ №c0ffee11. Aura Coffee"`. (This encodes the exact PDD §8.2 format: status text followed by the short-id repeat.) MUST fail in RED.

## 8. RED: REFACTOR group 7 (test_notification_messages.py)

- [x] 8.1 [core-api] REFACTOR: convert MATRIX into a list of dataclass instances (or keep as tuples with an `IDS` parametrize-id list) so pytest output labels each case by status+order_type+cancelled_by. Verify every test in the module still FAILs for the RED reason.

## 9. RED: sms-worker task structural tests (test_notification_task.py)

- [x] 9.1 [sms-worker] RED: add `test_task_is_registered_under_expected_name` — inside body `from sms_worker.tasks.notification import send_order_notification_sms`; assert `send_order_notification_sms.name == "sms_worker.send_order_notification_sms"`. MUST fail with `ImportError` in RED.
- [x] 9.2 [sms-worker] RED: add `test_task_retry_configuration_matches_pdd_7_8` — inspects task attributes; asserts `max_retries == 3`, `default_retry_delay == 2`, `retry_backoff is True`, `retry_backoff_max == 32`. MUST fail in RED.

## 10. RED: sms-worker task behavior tests (test_notification_task.py)

- [x] 10.1 [sms-worker] RED: add `test_success_updates_notification_to_sent` — arrange a Notification row with `channel=SMS, status=PENDING`, encrypt a known phone, monkeypatch `_TRANSPORT` (or its module-level binding) to return `True`; call `send_order_notification_sms.run(...)`; assert row's `status == SENT`, `sent_at` is a UTC datetime within the last 5 seconds. MUST fail in RED.
- [x] 10.2 [sms-worker] RED: add `test_decrypted_phone_is_passed_to_transport` — monkeypatch transport with a `MagicMock`; encrypt `+79991234567`; invoke task; assert `transport.call_args.args[0] == "+79991234567"`. MUST fail in RED.
- [x] 10.3 [sms-worker] RED: add `test_intermediate_failure_raises_for_retry` — transport returns `False`, stub `self.request.retries = 1`; assert `pytest.raises(Exception)` when invoking `.run(self_stub, ...)` and assert the Notification row's `status` remains `PENDING`. MUST fail in RED.
- [x] 10.4 [sms-worker] RED: add `test_exhausted_retries_marks_failed_and_does_not_raise` — transport returns `False`, stub `self.request.retries = 3`, `self.max_retries = 3`; assert the call returns normally (no exception) and Notification row's `status == FAILED`. MUST fail in RED.
- [x] 10.5 [sms-worker] RED: add `test_exhausted_retries_logs_error_with_notification_id` — same stub as 10.4, use `caplog` at ERROR level; assert at least one record whose `message` contains the first 8 chars of the notification id. MUST fail in RED.
- [x] 10.6 [sms-worker] RED: add `test_plaintext_phone_not_in_logs` (INV-013) — run success and failure paths with `caplog`; assert no record contains the plaintext phone string `"+79991234567"`. MUST fail in RED.
- [x] 10.7 [sms-worker] RED: add `test_missing_notification_row_logs_and_returns` — invoke task with a random UUID that does NOT exist; assert the task logs a warning and returns without raising (defensive: do not blow up the worker if a row was deleted). MUST fail in RED.

## 11. RED: REFACTOR group 9–10 (test_notification_task.py)

- [x] 11.1 [sms-worker] REFACTOR: extract a `_make_self_stub(retries, max_retries=3)` helper and a `_make_encrypted_phone(phone)` helper; rewrite tests in the module to use them. Verify every test still FAILs for the RED reason after the refactor.

## 12. VERIFY

- [x] 12.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_notification_service.py services/core-api/tests/test_notification_messages.py -v` and confirm every test fails (expected in RED). Count of failing tests MUST match the number of `RED:` tasks in groups 3–7 that create tests.
- [x] 12.2 [sms-worker] VERIFY: run `docker compose exec sms-worker pytest services/sms-worker/tests/test_notification_task.py -v` and confirm every test fails (expected in RED).
- [x] 12.3 VERIFY: run the full backend suite `docker compose exec core-api pytest services/core-api/tests/ -v` and confirm that no previously-passing test has regressed — RED additions are the only new failures.
