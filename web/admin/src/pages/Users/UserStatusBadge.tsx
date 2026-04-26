import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import type { UserStatus } from '@/api/admin-users';

// START_MODULE_CONTRACT
//   PURPOSE: Localized status badge for users — independent palette from order
//            status badges by design. Pure presentation.
//   SCOPE:   Used by UsersTable rows and UserDetailDialog header.
//   DEPENDS: react-i18next, ui Badge, @/api/admin-users (UserStatus).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UserStatusBadge - colored localized badge for UserStatus
// END_MODULE_MAP

interface Props {
  status: UserStatus;
}

// Своя палитра для UserStatus. Намеренно отдельный компонент —
// enum'ы и цвета не совпадают с бейджем для заказов.
export function UserStatusBadge({ status }: Props) {
  const { t } = useTranslation();
  const label = t(`pages.users.status.${status}`);
  const variant =
    status === 'active'
      ? 'default'
      : status === 'blocked'
        ? 'destructive'
        : status === 'pending_verification'
          ? 'warning'
          : 'muted'; // deleted
  return (
    <Badge variant={variant as never} data-testid={`user-status-${status}`}>
      {label}
    </Badge>
  );
}
