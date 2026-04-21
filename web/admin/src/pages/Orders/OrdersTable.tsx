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

interface OrdersTableProps {
  rows: OrderResponse[];
  onSelect: (id: string) => void;
  emptyLabel: string;
}

export function OrdersTable({ rows, onSelect, emptyLabel }: OrdersTableProps) {
  const { t } = useTranslation();

  if (rows.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-8 text-center">{emptyLabel}</p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('pages.orders.columns.id')}</TableHead>
          <TableHead>{t('pages.orders.columns.created_at')}</TableHead>
          <TableHead>{t('pages.orders.columns.type')}</TableHead>
          <TableHead>{t('pages.orders.columns.status')}</TableHead>
          <TableHead className="text-right">{t('pages.orders.columns.total')}</TableHead>
          <TableHead className="text-right">{t('pages.orders.columns.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id} data-testid={`order-row-${row.id}`}>
            <TableCell className="font-mono text-xs">{shortId(row.id)}</TableCell>
            <TableCell className="text-sm">{formatCreatedAt(row.created_at)}</TableCell>
            <TableCell>{t(`pages.orders.type.${row.type}`)}</TableCell>
            <TableCell>
              <StatusBadge status={row.status} />
            </TableCell>
            <TableCell className="text-right font-medium">
              {formatKopecks(row.total)}
            </TableCell>
            <TableCell className="text-right">
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
