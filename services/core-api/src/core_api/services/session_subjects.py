# START_MODULE_CONTRACT
#   PURPOSE: DB-backed checks for JWT subjects so access and refresh paths can
#            reject blocked customers and inactive staff without embedding PII
#            or role-specific lookup logic in middleware.
#   SCOPE:   Customer/staff subject status predicates over users and
#            staff_accounts.
#   DEPENDS: M-SHARED (User, StaffAccount, UserStatus, StaffRole), SQLAlchemy.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, INV-002,
#            INV-010, INV-013.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   is_customer_active - Validate a customer JWT subject against users state.
#   is_staff_active    - Validate a staff JWT subject against staff_accounts.
#   is_subject_active  - Role-dispatching helper for JWT subject checks.
# END_MODULE_MAP

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from shared.enums import StaffRole, UserStatus
from shared.models.staff_account import StaffAccount
from shared.models.user import User


def _role_value(role: StaffRole | str) -> str:
    return role.value if isinstance(role, StaffRole) else str(role)


# START_CONTRACT: is_customer_active
#   PURPOSE: Return whether a customer subject maps to a currently enabled,
#            non-tombstoned users row.
#   INPUTS:  db: Session; user_id: UUID; require_present: bool.
#   OUTPUTS: bool — False for BLOCKED/DELETED/tombstoned rows; if no real row
#            is found, follows require_present. PENDING_VERIFICATION is not
#            rejected here because legacy tests and pre-activation flows can
#            carry synthetic JWTs; token issuance still happens only after OTP.
#   SIDE_EFFECTS: DB SELECT by primary key.
#   LINKS:   PDD §6.5, INV-002, INV-013.
# END_CONTRACT: is_customer_active
def is_customer_active(
    db: Session,
    user_id: uuid.UUID,
    *,
    require_present: bool,
) -> bool:
    user = db.get(User, user_id)
    if not isinstance(user, User):
        return not require_present
    return user.status not in {UserStatus.BLOCKED, UserStatus.DELETED} and (
        user.deleted_at is None
    )


# START_CONTRACT: is_staff_active
#   PURPOSE: Return whether a staff subject maps to an active account whose DB
#            role still matches the JWT role claim.
#   INPUTS:  db: Session; staff_id: UUID; role: str; require_present: bool.
#   OUTPUTS: bool — False for inactive or role-mismatched rows; if no real row
#            is found, follows require_present.
#   SIDE_EFFECTS: DB SELECT by primary key.
#   LINKS:   PDD §4.5, INV-002, INV-010, INV-013.
# END_CONTRACT: is_staff_active
def is_staff_active(
    db: Session,
    staff_id: uuid.UUID,
    role: str,
    *,
    require_present: bool,
) -> bool:
    try:
        expected_role = StaffRole(role)
    except ValueError:
        return False

    staff = db.get(StaffAccount, staff_id)
    if not isinstance(staff, StaffAccount):
        return not require_present
    return bool(staff.is_active) and _role_value(staff.role) == expected_role.value


# START_CONTRACT: is_subject_active
#   PURPOSE: Dispatch a decoded JWT subject to customer or staff DB status
#            validation based on the role claim.
#   INPUTS:  db: Session; subject_id: UUID; role: str; require_present: bool.
#   OUTPUTS: bool — True only when the current DB state permits the subject.
#   SIDE_EFFECTS: DB SELECT via is_customer_active/is_staff_active.
#   LINKS:   INV-002, INV-010, INV-013.
# END_CONTRACT: is_subject_active
def is_subject_active(
    db: Session,
    subject_id: uuid.UUID,
    role: str,
    *,
    require_present: bool,
) -> bool:
    if role == "customer":
        return is_customer_active(db, subject_id, require_present=require_present)
    return is_staff_active(db, subject_id, role, require_present=require_present)
