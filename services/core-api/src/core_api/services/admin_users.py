# START_MODULE_CONTRACT
#   PURPOSE: Admin operations on User aggregate: list/detail, block/unblock with
#            cascade order cancellation, manual loyalty adjustment.
#   SCOPE:   Drives PDD §6.5 User Account Lifecycle (ACTIVE↔BLOCKED) and §7.6
#            cascade-cancel of in-flight orders on block. PII-safe: no phone
#            search, tombstoned users return 404.
#   DEPENDS: M-SHARED (User, UserProfile, LoyaltyAccount, LoyaltyTransaction,
#            Order), M-DATABASE, schemas.admin_users, services.order_cancel
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, §7.6,
#            INV-002, INV-004, INV-010, INV-013, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AdminUsersError          - base class for admin-users domain errors
#   UserNotFoundError        - id missing / tombstoned (INV-013)
#   InvalidUserStateError    - forbidden §6.5 transition or invalid src state
#   InsufficientBalanceError - adjust_loyalty would drive balance < 0
#   list_users               - paginated list with status/search filters
#   get_user_detail          - profile + loyalty + recent transactions
#   block_user               - ACTIVE→BLOCKED + cascade order cancel
#   unblock_user             - BLOCKED→ACTIVE
#   adjust_loyalty           - manual ADMIN_ADJUSTMENT loyalty txn (INV-004)
# END_MODULE_MAP
"""Сервисы admin-users-api (PDD §6.5, §7.1 item 2, §7.6).

Пять операций для оператора панели администратора:
    - list_users        → GET /api/v1/admin/users
    - get_user_detail   → GET /api/v1/admin/users/{user_id}
    - block_user        → POST /api/v1/admin/users/{user_id}/block
    - unblock_user      → POST /api/v1/admin/users/{user_id}/unblock
    - adjust_loyalty    → POST /api/v1/admin/users/{user_id}/loyalty/adjust

Инварианты:
    INV-004: balance UPDATE + LoyaltyTransaction INSERT — одна транзакция,
             SELECT … FOR UPDATE на loyalty_accounts.
    INV-010: сервис вызывается только из routers/admin_users.py, а там RBAC {ADMIN}.
    INV-013: phone_hash никогда не раскрывается и не ищется; tombstoned user → 404.
    INV-016: запрещённые переходы §6.5 отклоняются InvalidUserStateError.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from shared.enums import (
    LoyaltyTransactionType,
    OrderStatus,
    UserStatus,
)
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.loyalty_transaction import LoyaltyTransaction
from shared.models.order import Order
from shared.models.user import User
from shared.models.user_profile import UserProfile

from core_api.schemas.admin_users import (
    BlockUserResponse,
    LoyaltyAdjustResponse,
    LoyaltyTransactionItem,
    UserDetailResponse,
    UserListResponse,
    UserSummary,
)
from core_api.services.order_cancel import cancel_order

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Доменные ошибки
# ---------------------------------------------------------------------------


# START_CONTRACT: AdminUsersError
#   PURPOSE: Base class for all admin-users service domain errors.
#   INPUTS:  message: str (optional)
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: AdminUsersError
class AdminUsersError(Exception):
    """Базовый класс ошибок admin-users-api."""


# START_CONTRACT: UserNotFoundError
#   PURPOSE: Raised when target user id is missing or tombstoned (deleted_at IS
#            NOT NULL or status=DELETED). Tombstone variant enforces INV-013 —
#            PII never re-surfaces.
#   INPUTS:  message: str — typically the user id
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.5, INV-013
# END_CONTRACT: UserNotFoundError
class UserNotFoundError(AdminUsersError):
    """Пользователь не найден (или tombstoned — PII недоступны)."""


# START_CONTRACT: InvalidUserStateError
#   PURPOSE: Raised when an admin operation hits a forbidden §6.5 transition
#            (e.g. operating on PENDING_VERIFICATION/DELETED).
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.5, INV-016
# END_CONTRACT: InvalidUserStateError
class InvalidUserStateError(AdminUsersError):
    """Запрещённый §6.5 переход или состояние для операции."""


# START_CONTRACT: InsufficientBalanceError
#   PURPOSE: Raised by adjust_loyalty when delta would drive balance negative.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: InsufficientBalanceError
class InsufficientBalanceError(AdminUsersError):
    """adjust_loyalty: new_balance < 0 → 422."""


# ---------------------------------------------------------------------------
# Каскад-фильтр block_user (§7.6: IN_DELIVERY не отменяем админом)
# ---------------------------------------------------------------------------

_CANCELLABLE_ON_BLOCK: set[OrderStatus] = {
    OrderStatus.CREATED,
    OrderStatus.PAID,
    OrderStatus.PREPARING,
    OrderStatus.READY,
}

_FORBIDDEN_USER_STATES: set[UserStatus] = {
    UserStatus.PENDING_VERIFICATION,
    UserStatus.DELETED,
}


def _forbidden_state(user: User) -> bool:
    return user.deleted_at is not None or user.status in _FORBIDDEN_USER_STATES


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------


def _status_predicate(status_filter: str):
    """Строит WHERE-фрагмент для фильтра статуса (дизайн D4)."""
    if status_filter == "active":
        return and_(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
    if status_filter == "blocked":
        return and_(User.status == UserStatus.BLOCKED, User.deleted_at.is_(None))
    if status_filter == "pending_verification":
        return and_(
            User.status == UserStatus.PENDING_VERIFICATION,
            User.deleted_at.is_(None),
        )
    if status_filter == "deleted":
        return or_(User.status == UserStatus.DELETED, User.deleted_at.is_not(None))
    # "all" — без фильтра
    return None


# START_CONTRACT: list_users
#   PURPOSE: Paginated user list for admin panel with status filter and optional
#            display_name prefix search. Never reads or matches phone fields.
#   INPUTS:  db: Session
#            status: str — "all"|"active"|"blocked"|"pending_verification"|"deleted"
#            search: str|None — case-insensitive prefix on display_name
#            page, per_page: int — pagination
#   OUTPUTS: UserListResponse (items + total_count + page meta)
#   SIDE_EFFECTS: DB SELECT only.
#   LINKS:   PDD §4.5, §6.5, INV-013 (no PII search), INV-010
# END_CONTRACT: list_users
def list_users(
    db: Session,
    *,
    status: str = "all",
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> UserListResponse:
    """Пагинированный список пользователей с опциональным поиском по display_name.

    INV-013: `search` работает ТОЛЬКО по `user_profiles.display_name` (case-insensitive
    prefix). Никаких обращений к `phone` / `phone_hash`.
    """
    base_where: list = []
    pred = _status_predicate(status)
    if pred is not None:
        base_where.append(pred)

    # Для фильтра search нам нужен JOIN на user_profiles — и в count, и в main.
    search_joined = search is not None and len(search) > 0

    # --- total_count ---
    count_stmt: Select = select(func.count()).select_from(User)
    if search_joined:
        count_stmt = count_stmt.join(
            UserProfile, UserProfile.user_id == User.id, isouter=False
        )
        base_where.append(
            func.lower(UserProfile.display_name).like(search.lower() + "%")
        )
    if base_where:
        count_stmt = count_stmt.where(*base_where)
    total_count = db.execute(count_stmt).scalar_one()

    # --- items ---
    loyalty_balance_expr = func.coalesce(LoyaltyAccount.balance, 0).label(
        "loyalty_balance"
    )
    items_stmt = (
        select(
            User.id,
            User.status,
            User.created_at,
            UserProfile.display_name,
            loyalty_balance_expr,
        )
        .select_from(User)
        .join(UserProfile, UserProfile.user_id == User.id, isouter=not search_joined)
        .join(
            LoyaltyAccount, LoyaltyAccount.user_id == User.id, isouter=True
        )
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if base_where:
        items_stmt = items_stmt.where(*base_where)

    rows = db.execute(items_stmt).all()
    items = [
        UserSummary(
            id=row.id,
            status=row.status.value if hasattr(row.status, "value") else row.status,
            display_name=row.display_name,
            loyalty_balance=int(row.loyalty_balance or 0),
            created_at=row.created_at,
        )
        for row in rows
    ]
    return UserListResponse(
        items=items,
        total_count=int(total_count),
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# get_user_detail
# ---------------------------------------------------------------------------


# START_CONTRACT: get_user_detail
#   PURPOSE: Full admin view of a single user: status, profile, loyalty balance,
#            last 20 loyalty transactions, count of active orders.
#   INPUTS:  db: Session
#            user_id: UUID
#   OUTPUTS: UserDetailResponse
#   SIDE_EFFECTS: DB SELECTs only; tombstoned → UserNotFoundError (INV-013).
#   LINKS:   PDD §6.5, INV-013
# END_CONTRACT: get_user_detail
def get_user_detail(db: Session, user_id: uuid.UUID) -> UserDetailResponse:
    """Полная карточка пользователя для админки.

    Tombstoned (deleted_at IS NOT NULL) → UserNotFoundError (INV-013).
    """
    user = db.execute(
        select(User)
        .options(joinedload(User.profile), joinedload(User.loyalty_account))
        .where(User.id == user_id)
    ).scalar_one_or_none()

    if user is None or user.deleted_at is not None:
        raise UserNotFoundError(str(user_id))

    profile = user.profile
    account = user.loyalty_account

    tx_rows = db.scalars(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.user_id == user_id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(20)
    ).all()

    active_orders_count = db.execute(
        select(func.count())
        .select_from(Order)
        .where(
            Order.user_id == user_id,
            Order.status.notin_({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
        )
    ).scalar_one()

    return UserDetailResponse(
        id=user.id,
        status=user.status.value,
        display_name=profile.display_name if profile else None,
        language=profile.preferred_language if profile else "ru",
        created_at=user.created_at,
        loyalty_balance=account.balance if account else 0,
        loyalty_transactions=[
            LoyaltyTransactionItem.model_validate(tx) for tx in tx_rows
        ],
        active_orders_count=int(active_orders_count),
    )


# ---------------------------------------------------------------------------
# block_user
# ---------------------------------------------------------------------------


# START_CONTRACT: block_user
#   PURPOSE: State transition ACTIVE → BLOCKED with cascade cancellation of
#            in-flight orders (CREATED/PAID/PREPARING/READY). Idempotent on
#            already-BLOCKED. IN_DELIVERY orders are skipped silently.
#   INPUTS:  db: Session
#            user_id: UUID
#   OUTPUTS: BlockUserResponse — final status + cancelled_orders_count
#   SIDE_EFFECTS: DB UPDATE users.status; FOR UPDATE row lock; per-order cancel
#                 delegated to cancel_order (each its own atomic txn under
#                 INV-004). Source state: ACTIVE. Target state: BLOCKED.
#   LINKS:   PDD §6.5, §7.6, INV-004, INV-005, INV-016
# END_CONTRACT: block_user
def block_user(db: Session, user_id: uuid.UUID) -> BlockUserResponse:
    """ACTIVE → BLOCKED + каскад отмены {CREATED, PAID, PREPARING, READY}.

    IN_DELIVERY skip silently — курьер доделает. Идемпотентен на BLOCKED.
    Per-order atomicity делегируется `cancel_order` (INV-004 scope).
    """
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(str(user_id))
    if _forbidden_state(user):
        raise InvalidUserStateError("invalid_user_state")
    if user.status == UserStatus.BLOCKED:
        return BlockUserResponse(
            user_id=user.id, status="blocked", cancelled_orders_count=0
        )

    user.status = UserStatus.BLOCKED
    db.flush()
    db.commit()

    orders_to_cancel = db.scalars(
        select(Order).where(
            Order.user_id == user_id,
            Order.status.in_(_CANCELLABLE_ON_BLOCK),
        )
    ).all()

    cancelled = 0
    for order in orders_to_cancel:
        cancel_order(
            order_id=order.id,
            cancelled_by="admin",
            reason="user_blocked",
            db_session=db,
        )
        cancelled += 1

    if cancelled > 10:
        logger.warning(
            "block_user cascade cancelled %d orders for user %s", cancelled, user_id
        )

    return BlockUserResponse(
        user_id=user.id, status="blocked", cancelled_orders_count=cancelled
    )


# ---------------------------------------------------------------------------
# unblock_user
# ---------------------------------------------------------------------------


# START_CONTRACT: unblock_user
#   PURPOSE: State transition BLOCKED → ACTIVE. Idempotent on already-ACTIVE.
#            Does not undo prior cascade-cancellations.
#   INPUTS:  db: Session, user_id: UUID
#   OUTPUTS: BlockUserResponse — status="active", cancelled_orders_count=0
#   SIDE_EFFECTS: DB UPDATE users.status + commit. Source: BLOCKED. Target: ACTIVE.
#   LINKS:   PDD §6.5, INV-016
# END_CONTRACT: unblock_user
def unblock_user(db: Session, user_id: uuid.UUID) -> BlockUserResponse:
    """BLOCKED → ACTIVE. Без каскада — CANCELLED заказы остаются CANCELLED."""
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(str(user_id))
    if _forbidden_state(user):
        raise InvalidUserStateError("invalid_user_state")
    if user.status == UserStatus.ACTIVE:
        return BlockUserResponse(
            user_id=user.id, status="active", cancelled_orders_count=0
        )

    user.status = UserStatus.ACTIVE
    db.commit()
    return BlockUserResponse(
        user_id=user.id, status="active", cancelled_orders_count=0
    )


# ---------------------------------------------------------------------------
# adjust_loyalty
# ---------------------------------------------------------------------------


# START_CONTRACT: adjust_loyalty
#   PURPOSE: Manual ADMIN_ADJUSTMENT loyalty txn — atomically updates balance
#            and inserts a LoyaltyTransaction row.
#   INPUTS:  db: Session
#            user_id: UUID
#            delta: int — signed point delta
#            reason: str — free-text description stored on the transaction
#   OUTPUTS: LoyaltyAdjustResponse — transaction_id, new_balance, delta
#   SIDE_EFFECTS: SELECT FOR UPDATE on user + loyalty_account; UPDATE balance +
#                 INSERT loyalty_transaction in a single txn (INV-004).
#                 Negative result → InsufficientBalanceError (rolled back).
#   LINKS:   PDD §6.5, INV-004, INV-013
# END_CONTRACT: adjust_loyalty
def adjust_loyalty(
    db: Session,
    user_id: uuid.UUID,
    delta: int,
    reason: str,
) -> LoyaltyAdjustResponse:
    """ADMIN_ADJUSTMENT: balance UPDATE + LoyaltyTransaction INSERT в одной tx (INV-004).

    BLOCKED принимается — легитимный workflow "вернуть баллы перед unblock".
    """
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(str(user_id))
    if _forbidden_state(user):
        raise InvalidUserStateError("invalid_user_state")

    account = db.execute(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if account is None:
        # Non-goal: не создаём LoyaltyAccount автоматически — это silent state repair.
        raise UserNotFoundError(str(user_id))

    new_balance = account.balance + delta
    if new_balance < 0:
        raise InsufficientBalanceError("insufficient_balance")

    account.balance = new_balance
    tx = LoyaltyTransaction(
        user_id=user_id,
        order_id=None,
        type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        amount=delta,
        balance_after=new_balance,
        description=reason,
    )
    db.add(tx)
    db.flush()
    db.commit()

    return LoyaltyAdjustResponse(
        transaction_id=tx.id, new_balance=new_balance, delta=delta
    )
