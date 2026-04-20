"""Фабричные функции для admin-users-api тестов (PDD §6.5, §7.1 item 2).

Сеют `User` + `UserProfile` (+ опционально `LoyaltyAccount`) напрямую через
ORM, без захода в бизнес-сервисы. Используются тестами test_admin_users_*.

Важно: поле `phone` в `user_profiles` — LargeBinary NOT NULL (INV-013:
PII хранится только в зашифрованном виде). В тестах кладём детерминированный
bytes-stub — админские маршруты его всё равно не раскрывают.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from shared.enums import UserStatus
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.user import User
from shared.models.user_profile import UserProfile


def make_user_with_profile(
    session: Session,
    *,
    status: UserStatus = UserStatus.ACTIVE,
    display_name: str | None = None,
    preferred_language: str = "ru",
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    phone_hash: str | None = None,
) -> User:
    """Создаёт User + связанный UserProfile с контролируемыми полями.

    - `phone_hash`: если None — случайный hex; иначе используется как есть
      (полезно в тестах INV-013 guard, где явно сеется "abcdef..." префикс).
    - `phone`: bytes-stub, не декодируется в тестах.
    """
    user = User(
        phone_hash=phone_hash if phone_hash is not None else secrets.token_hex(32),
        status=status,
    )
    if created_at is not None:
        user.created_at = created_at
    if deleted_at is not None:
        user.deleted_at = deleted_at
    session.add(user)
    session.flush()

    profile = UserProfile(
        user_id=user.id,
        phone=b"stub-encrypted-phone",
        display_name=display_name,
        preferred_language=preferred_language,
    )
    session.add(profile)
    session.flush()
    return user


def make_user_with_loyalty_and_profile(
    session: Session,
    *,
    balance: int = 0,
    **user_kwargs,
) -> tuple[User, LoyaltyAccount]:
    """User + UserProfile + LoyaltyAccount(balance) одной операцией."""
    user = make_user_with_profile(session, **user_kwargs)
    account = LoyaltyAccount(user_id=user.id, balance=balance)
    session.add(account)
    session.flush()
    return user, account


def seed_admin_users_across_statuses(
    session: Session,
    counts: dict[UserStatus, int],
    *,
    base_time: datetime | None = None,
    step: timedelta = timedelta(minutes=1),
) -> dict[UserStatus, list[uuid.UUID]]:
    """Сеет users под каждый UserStatus с монотонным created_at для DESC-ассертов.

    Возвращает словарь {UserStatus: [user_id, ...]} — order of insert == ASC by
    created_at; тесты reverse-ят при необходимости.
    """
    if base_time is None:
        total = sum(counts.values())
        base_time = datetime.now(tz=UTC) - step * max(total, 1)

    result: dict[UserStatus, list[uuid.UUID]] = {}
    cursor = 0
    for status, n in counts.items():
        ids: list[uuid.UUID] = []
        for i in range(n):
            t = base_time + step * cursor
            user = make_user_with_profile(
                session,
                status=status,
                display_name=f"user-{status.value}-{i}",
                created_at=t,
            )
            ids.append(user.id)
            cursor += 1
        result[status] = ids

    session.commit()
    return result
