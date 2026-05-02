import { useTranslation } from 'react-i18next';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { StatusBadge } from './StatusBadge';
import type { OrderResponse } from '@/api/admin-orders';

// START_MODULE_CONTRACT
//   PURPOSE: Render the orders list as a table with status badge, formatted
//            kopecks total, short id and a Details button. Pure presentation.
//   SCOPE:   Used only by OrdersPage.
//   DEPENDS: react-i18next, ui primitives, ./StatusBadge, @/api/admin-orders type.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §5.2 (kopecks),
//            INV-014 (item snapshot fields visible from row → dialog).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrdersTable - clickable orders table, calls onSelect with row id
// END_MODULE_MAP

// Копейки → "350,00 ₽" локалью ru-RU. Модуль-приватный хелпер: нам нужен
// один и тот же формат в списке и в детальной модалке — держим код DRY,
// но не поднимаем его в @/lib до тех пор, пока его не потребует ещё один
// экран (ровно одно предупреждение «don't design for hypothetical…»).
const moneyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
});

function formatKopecks(kopecks: number): string {
  return moneyFormatter.format(kopecks / 100);
}

function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

const mobileLabelClass =
  'text-xs font-medium uppercase tracking-wide text-muted-foreground md:hidden';
const responsiveRowClass =
  'block rounded-lg border bg-card p-3 shadow-sm md:table-row md:rounded-none md:border-b md:bg-transparent md:p-0 md:shadow-none';
const responsiveCellClass =
  'flex items-center justify-between gap-4 py-2 text-sm md:table-cell md:p-2';

interface OrdersTableProps {
  rows: OrderResponse[];
  onSelect: (id: string) => void;
  emptyLabel: string;
}

export function OrdersTable({ rows, onSelect, emptyLabel }: OrdersTableProps) {
  const { t } = useTranslation();

  if (rows.length === 0) {
    return (
      <p className="text-muted-foreground py-8 text-center text-sm">
        {emptyLabel}
      </p>
    );
  }

  return (
    <Table className="block md:table">
      <TableHeader className="hidden md:table-header-group">
        <TableRow>
          <TableHead>{t('pages.orders.columns.id')}</TableHead>
          <TableHead>{t('pages.orders.columns.created_at')}</TableHead>
          <TableHead>{t('pages.orders.columns.type')}</TableHead>
          <TableHead>{t('pages.orders.columns.status')}</TableHead>
          <TableHead className="text-right">
            {t('pages.orders.columns.total')}
          </TableHead>
          <TableHead className="text-right">
            {t('pages.orders.columns.actions')}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody className="block space-y-3 md:table-row-group md:space-y-0">
        {rows.map((row) => (
          <TableRow
            key={row.id}
            className={responsiveRowClass}
            data-testid={`order-row-${row.id}`}
          >
            <TableCell className={responsiveCellClass}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.id')}
              </span>
              <span className="font-mono text-xs">{shortId(row.id)}</span>
            </TableCell>
            <TableCell className={responsiveCellClass}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.created_at')}
              </span>
              <span className="text-right md:text-left">
                {formatCreatedAt(row.created_at)}
              </span>
            </TableCell>
            <TableCell className={responsiveCellClass}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.type')}
              </span>
              <span>{t(`pages.orders.type.${row.type}`)}</span>
            </TableCell>
            <TableCell className={responsiveCellClass}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.status')}
              </span>
              <span>
                <StatusBadge status={row.status} />
              </span>
            </TableCell>
            <TableCell className={`${responsiveCellClass} md:text-right`}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.total')}
              </span>
              <span className="font-medium">{formatKopecks(row.total)}</span>
            </TableCell>
            <TableCell className={`${responsiveCellClass} md:text-right`}>
              <span className={mobileLabelClass}>
                {t('pages.orders.columns.actions')}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelect(row.id)}
                data-testid={`order-details-${row.id}`}
              >
                {t('pages.orders.actions.details')}
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
