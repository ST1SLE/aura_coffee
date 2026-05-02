# START_MODULE_CONTRACT
#   PURPOSE: Account deletion/anonymization boundary for customer-requested and
#            admin-requested PDD §6.5 transitions into DELETED.
#   SCOPE:   In-place tombstone strategy: preserve opaque users.id for historic
#            FKs, scrub phone lookup hash, remove PII sibling rows, zero loyalty,
#            revoke eligibility through status/deleted_at, and cascade-cancel
#            cancellable active orders before final tombstoning.
#   DEPENDS: M-SHARED (User, UserProfile, DeliveryAddress, LoyaltyAccount,
#            LoyaltyTransaction, Order), M-DATABASE, services.order_cancel,
#            schemas.account_deletion.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.1, §6.1, §6.5,
#            §7.6, INV-004, INV-013, INV-016.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AccountDeletionError            - base deletion domain error
#   AccountDeletionNotFoundError    - target user missing
#   AccountDeletionInvalidStateError - source state not allowed for deletion
#   AccountDeletionActiveOrderError - IN_DELIVERY order blocks PII deletion
#   delete_customer_account         - ACTIVE→DELETED customer self-delete
#   delete_blocked_customer_account - BLOCKED→DELETED admin delete
# END_MODULE_MAP
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.schemas.account_deletion import AccountDeletionResponse
from core_api.services.order_cancel import cancel_order
from shared.enums import LoyaltyTransactionType, OrderStatus, UserStatus
from shared.grace.logging import get_grace_logger
from shared.models.delivery_address import DeliveryAddress
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.loyalty_transaction import LoyaltyTransaction
from shared.models.order import Order
from shared.models.user import User
from shared.models.user_profile import UserProfile

_grace_log = get_grace_logger("CoreApi")

_CANCELLABLE_ON_DELETE: set[OrderStatus] = {
    OrderStatus.CREATED,
    OrderStatus.PAID,
    OrderStatus.PREPARING,
    OrderStatus.READY,
}

_BLOCKING_ON_DELETE: set[OrderStatus] = {OrderStatus.IN_DELIVERY}


# START_CONTRACT: AccountDeletionError
#   PURPOSE: Base class for account-deletion domain errors.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: AccountDeletionError
class AccountDeletionError(Exception):
    """Base class for account deletion errors."""


# START_CONTRACT: AccountDeletionNotFoundError
#   PURPOSE: Raised when the target user row does not exist.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: AccountDeletionNotFoundError
class AccountDeletionNotFoundError(AccountDeletionError):
    """Target user does not exist."""


# START_CONTRACT: AccountDeletionInvalidStateError
#   PURPOSE: Raised when PDD §6.5 source state does not allow deletion.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.5, INV-016.
# END_CONTRACT: AccountDeletionInvalidStateError
class AccountDeletionInvalidStateError(AccountDeletionError):
    """Deletion source state is not allowed."""


# START_CONTRACT: AccountDeletionActiveOrderError
#   PURPOSE: Raised when an IN_DELIVERY order blocks account deletion because
#            PDD §6.1 forbids IN_DELIVERY→CANCELLED.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.1, §6.5, INV-016.
# END_CONTRACT: AccountDeletionActiveOrderError
class AccountDeletionActiveOrderError(AccountDeletionError):
    """Deletion cannot proceed while an order is already in delivery."""


def _tombstone_phone_hash(user_id: uuid.UUID) -> str:
    return hashlib.sha256(f"deleted:{user_id}".encode("ascii")).hexdigest()


def _load_existing_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AccountDeletionNotFoundError(str(user_id))
    return user


def _validate_source_state(
    user: User,
    allowed_sources: set[UserStatus],
) -> None:
    if user.deleted_at is not None or user.status == UserStatus.DELETED:
        raise AccountDeletionInvalidStateError("invalid_user_state")
    if user.status not in allowed_sources:
        raise AccountDeletionInvalidStateError("invalid_user_state")


def _raise_if_blocking_orders(db: Session, user_id: uuid.UUID) -> None:
    blocking_id = db.scalars(
        select(Order.id)
        .where(
            Order.user_id == user_id,
            Order.status.in_(_BLOCKING_ON_DELETE),
        )
        .limit(1)
    ).first()
    if blocking_id is not None:
        raise AccountDeletionActiveOrderError("active_order_not_deletable")


def _cancel_cancellable_orders(db: Session, user_id: uuid.UUID) -> int:
    order_ids = list(
        db.scalars(
            select(Order.id).where(
                Order.user_id == user_id,
                Order.status.in_(_CANCELLABLE_ON_DELETE),
            )
        ).all()
    )

    for order_id in order_ids:
        cancel_order(
            order_id=order_id,
            cancelled_by="admin",
            reason="account_deleted",
            db_session=db,
        )
    return len(order_ids)


def _zero_loyalty(db: Session, user_id: uuid.UUID) -> None:
    account = db.execute(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if account is None:
        return

    old_balance = int(account.balance or 0)
    if old_balance != 0:
        db.add(
            LoyaltyTransaction(
                user_id=user_id,
                order_id=None,
                type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
                amount=-old_balance,
                balance_after=0,
                description="account_deleted",
            )
        )
    account.balance = 0


def _delete_account(
    *,
    db: Session,
    user_id: uuid.UUID,
    allowed_sources: set[UserStatus],
    fn: str,
) -> AccountDeletionResponse:
    user = _load_existing_user(db, user_id)
    _validate_source_state(user, allowed_sources)
    _raise_if_blocking_orders(db, user_id)
    cancelled_count = _cancel_cancellable_orders(db, user_id)

    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise AccountDeletionNotFoundError(str(user_id))
    _validate_source_state(user, allowed_sources)

    source_status = user.status.value
    _grace_log.block(
        fn,
        "BLOCK_TX_BEGIN",
        "account deletion tombstone begin",
        user_id=str(user.id),
        cancelled_orders_count=cancelled_count,
    )

    user.phone_hash = _tombstone_phone_hash(user.id)
    user.status = UserStatus.DELETED
    user.deleted_at = datetime.now(UTC)

    profile_rows = db.query(UserProfile).filter(UserProfile.user_id == user_id).delete(
        synchronize_session=False
    )
    address_rows = db.query(DeliveryAddress).filter(
        DeliveryAddress.user_id == user_id
    ).delete(synchronize_session=False)
    _zero_loyalty(db, user_id)

    db.flush()
    _grace_log.belief(
        fn,
        "BLOCK_STATE_TRANSITION",
        belief=UserStatus.DELETED.value,
        actual=user.status.value,
        user_id=str(user.id),
        source=source_status,
    )
    db.commit()
    _grace_log.block(
        fn,
        "BLOCK_TX_COMMIT",
        "account deletion tombstone committed",
        user_id=str(user.id),
        cancelled_orders_count=cancelled_count,
        pii_rows_removed=profile_rows + address_rows,
    )

    return AccountDeletionResponse(
        user_id=user.id,
        status="deleted",
        cancelled_orders_count=cancelled_count,
        pii_rows_removed=profile_rows + address_rows,
    )


# START_CONTRACT: delete_customer_account
#   PURPOSE: Customer self-service account deletion: ACTIVE→DELETED with
#            cancellable active-order unwind, PII removal, loyalty zeroing, and
#            in-place tombstone.
#   INPUTS:  db: Session; user_id: UUID
#   OUTPUTS: AccountDeletionResponse
#   SIDE_EFFECTS: Cancellable order cancellations/refund enqueue via
#                 services.order_cancel; DB UPDATE users, DELETE PII sibling
#                 rows, loyalty zeroing transaction; commit.
#   LINKS:   PDD §6.5, §7.6, INV-004, INV-013, INV-016.
# END_CONTRACT: delete_customer_account
def delete_customer_account(
    db: Session,
    user_id: uuid.UUID,
) -> AccountDeletionResponse:
    return _delete_account(
        db=db,
        user_id=user_id,
        allowed_sources={UserStatus.ACTIVE},
        fn="profile.delete",
    )


# START_CONTRACT: delete_blocked_customer_account
#   PURPOSE: Admin deletion of a blocked customer: BLOCKED→DELETED with the
#            same tombstone/PII/loyalty cleanup as customer self-delete.
#   INPUTS:  db: Session; user_id: UUID
#   OUTPUTS: AccountDeletionResponse
#   SIDE_EFFECTS: Cancellable order cancellations/refund enqueue via
#                 services.order_cancel; DB UPDATE users, DELETE PII sibling
#                 rows, loyalty zeroing transaction; commit.
#   LINKS:   PDD §6.5, INV-002, INV-010, INV-013, INV-016.
# END_CONTRACT: delete_blocked_customer_account
def delete_blocked_customer_account(
    db: Session,
    user_id: uuid.UUID,
) -> AccountDeletionResponse:
    return _delete_account(
        db=db,
        user_id=user_id,
        allowed_sources={UserStatus.BLOCKED},
        fn="admin.users.delete",
    )
