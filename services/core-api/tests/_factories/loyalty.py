"""Фабричные функции для тестов loyalty-API.

Создают минимальный набор ORM-сущностей (User, LoyaltyAccount,
LoyaltyTransaction) без захода в бизнес-логику сервисов. Используются
тестами test_profile_loyalty_* для прямого посева данных.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from shared.enums import LoyaltyTransactionType, UserStatus
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.loyalty_transaction import LoyaltyTransaction
from shared.models.user import User


def make_user_active(session: Session) -> User:
    """Минимальный ACTIVE-user без LoyaltyAccount."""
    user = User(phone_hash=secrets.token_hex(32), status=UserStatus.ACTIVE)
    session.add(user)
    session.flush()
    return user


def seed_loyalty_account(
    session: Session, *, user: User, balance: int = 0
) -> LoyaltyAccount:
    """Создаёт LoyaltyAccount с заданным balance для существующего user-а."""
    account = LoyaltyAccount(user_id=user.id, balance=balance)
    session.add(account)
    session.flush()
    return account


def make_user_with_loyalty(
    session: Session, *, balance: int = 0
) -> tuple[User, LoyaltyAccount]:
    """User(ACTIVE) + LoyaltyAccount(balance) одной операцией."""
    user = make_user_active(session)
    account = seed_loyalty_account(session, user=user, balance=balance)
    return user, account


def seed_loyalty_transaction(
    session: Session,
    *,
    user: User,
    type: LoyaltyTransactionType,
    amount: int,
    balance_after: int,
    order_id: uuid.UUID | None = None,
    description: str | None = None,
    created_at: datetime | None = None,
) -> LoyaltyTransaction:
    """Сеет одну LoyaltyTransaction row.

    `created_at=None` → подставляем текущее UTC (+ микросекунду, чтобы
    вызов в цикле давал монотонные значения без коллизий индекса).
    """
    tx = LoyaltyTransaction(
        id=uuid.uuid4(),
        user_id=user.id,
        order_id=order_id,
        type=type,
        amount=amount,
        balance_after=balance_after,
        description=description,
        created_at=created_at or datetime.now(tz=UTC),
    )
    session.add(tx)
    session.flush()
    return tx


@dataclass
class SeededTransactions:
    """Результат seed_n_transactions — id и created_at в порядке вставки (ASC)."""

    ids: list[uuid.UUID]
    created_ats: list[datetime]


def seed_n_transactions(
    session: Session,
    *,
    user: User,
    count: int,
    type: LoyaltyTransactionType = LoyaltyTransactionType.ACCRUAL,
    amount: int = 10,
    base_time: datetime | None = None,
) -> SeededTransactions:
    """N транзакций одного типа с монотонно растущим created_at."""
    from datetime import timedelta

    step = timedelta(seconds=1)
    t0 = base_time or (datetime.now(tz=UTC) - step * count)

    ids: list[uuid.UUID] = []
    created_ats: list[datetime] = []
    running_balance = 0
    for i in range(count):
        running_balance += amount
        ts = t0 + step * i
        tx = seed_loyalty_transaction(
            session,
            user=user,
            type=type,
            amount=amount,
            balance_after=running_balance,
            created_at=ts,
        )
        ids.append(tx.id)
        created_ats.append(ts)
    return SeededTransactions(ids=ids, created_ats=created_ats)
