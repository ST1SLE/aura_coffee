import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import type { UserStatus } from '@/api/admin-users';

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
