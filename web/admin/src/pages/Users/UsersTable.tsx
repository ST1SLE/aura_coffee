import { useTranslation } from 'react-i18next';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import type { UserSummary } from '@/api/admin-users';
import { UserStatusBadge } from './UserStatusBadge';

// START_MODULE_CONTRACT
//   PURPOSE: Render the paginated users list as a clickable table. Pure
//            presentation given items + onSelect callback.
//   SCOPE:   Used only by UsersPage.
//   DEPENDS: react-i18next, ui Table + Button, @/api/admin-users type, ./UserStatusBadge.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, INV-013 (display_name only,
//            no PII columns).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   UsersTable - clickable users list with status badge and balance column
// END_MODULE_MAP

interface Props {
  items: UserSummary[];
  onSelect: (userId: string) => void;
  emptyLabel: string;
}

function formatCreatedAt(iso: string, locale: string): string {
  try {
    return new Date(iso).toLocaleString(locale);
  } catch {
    return iso;
  }
}

export function UsersTable({ items, onSelect, emptyLabel }: Props) {
  const { t, i18n } = useTranslation();

  if (items.length === 0) {
    return (
      <p
        className="text-muted-foreground text-sm py-8 text-center"
        data-testid="users-empty"
      >
        {emptyLabel}
      </p>
    );
  }

  const balanceFormatter = new Intl.NumberFormat(i18n.language);
  const balanceUnit = t('pages.users.balance_unit_short');

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('pages.users.columns.name')}</TableHead>
          <TableHead>{t('pages.users.columns.status')}</TableHead>
          <TableHead>{t('pages.users.columns.balance')}</TableHead>
          <TableHead>{t('pages.users.columns.created_at')}</TableHead>
          <TableHead className="text-right">
            {t('pages.users.columns.actions')}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((user) => (
          <TableRow
            key={user.id}
            data-testid={`user-row-${user.id}`}
            className="cursor-pointer"
            onClick={() => onSelect(user.id)}
          >
            <TableCell className="font-medium">{user.display_name}</TableCell>
            <TableCell>
              <UserStatusBadge status={user.status} />
            </TableCell>
            <TableCell
              data-testid={`user-balance-${user.id}`}
            >{`${balanceFormatter.format(user.loyalty_balance)} ${balanceUnit}`}</TableCell>
            <TableCell>
              {formatCreatedAt(user.created_at, i18n.language)}
            </TableCell>
            <TableCell
              className="text-right"
              onClick={(e) => e.stopPropagation()}
            >
              <Button
                size="sm"
                variant="outline"
                onClick={() => onSelect(user.id)}
              >
                {t('pages.users.detail.details')}
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
