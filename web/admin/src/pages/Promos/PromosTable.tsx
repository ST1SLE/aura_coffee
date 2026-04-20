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
import { Badge } from '@/components/ui/badge';
import type {
  PromocodeResponse,
  PromocodeState,
} from '@/api/promocodes';

interface Props {
  items: PromocodeResponse[];
  onRowClick: (promo: PromocodeResponse) => void;
  onActivate: (promo: PromocodeResponse) => void;
  onDeactivate: (promo: PromocodeResponse) => void;
  pendingId?: string | null;
  emptyLabel: string;
}

function StateChip({ state }: { state: PromocodeState }) {
  const { t } = useTranslation();
  const label = t(`pages.promos.state_chip.${state}`);
  // Цветовое картирование — серверный state → shadcn badge variant.
  const variant =
    state === 'active'
      ? 'default'
      : state === 'inactive'
        ? 'muted'
        : state === 'expired'
          ? 'destructive'
          : 'warning'; // exhausted
  return <Badge variant={variant as never}>{label}</Badge>;
}

function formatDiscount(promo: PromocodeResponse): string {
  if (promo.discount_type === 'percent') return `${promo.discount_value}%`;
  const rubles = (promo.discount_value / 100).toFixed(2).replace(/\.00$/, '');
  return `${rubles} ₽`;
}

function formatValidUntil(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatUses(current: number, max: number | null): string {
  return `${current} / ${max ?? '∞'}`;
}

export function PromosTable({
  items,
  onRowClick,
  onActivate,
  onDeactivate,
  pendingId,
  emptyLabel,
}: Props) {
  const { t } = useTranslation();

  if (items.length === 0) {
    return <p className="text-muted-foreground text-sm py-8 text-center">{emptyLabel}</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('pages.promos.columns.code')}</TableHead>
          <TableHead>{t('pages.promos.columns.state')}</TableHead>
          <TableHead>{t('pages.promos.columns.discount')}</TableHead>
          <TableHead>{t('pages.promos.columns.valid_until')}</TableHead>
          <TableHead>{t('pages.promos.columns.uses')}</TableHead>
          <TableHead className="text-right">{t('pages.promos.columns.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((promo) => {
          const isPending = pendingId === promo.id;
          const canActivate = promo.state === 'inactive';
          const canDeactivate = promo.state === 'active';
          const validUntilClass =
            promo.state === 'expired' ? 'text-muted-foreground' : '';
          return (
            <TableRow
              key={promo.id}
              className="cursor-pointer"
              onClick={() => onRowClick(promo)}
              data-testid={`promo-row-${promo.code}`}
            >
              <TableCell className="font-mono">{promo.code}</TableCell>
              <TableCell>
                <StateChip state={promo.state} />
              </TableCell>
              <TableCell>{formatDiscount(promo)}</TableCell>
              <TableCell className={validUntilClass} data-testid={`valid-until-${promo.code}`}>
                {formatValidUntil(promo.valid_until)}
              </TableCell>
              <TableCell>{formatUses(promo.current_uses, promo.max_uses)}</TableCell>
              <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                <div className="flex gap-2 justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onRowClick(promo)}
                  >
                    {t('pages.promos.actions.edit')}
                  </Button>
                  {canActivate && (
                    <Button
                      size="sm"
                      disabled={isPending}
                      onClick={() => onActivate(promo)}
                    >
                      {t('pages.promos.actions.activate')}
                    </Button>
                  )}
                  {canDeactivate && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={isPending}
                      onClick={() => onDeactivate(promo)}
                    >
                      {t('pages.promos.actions.deactivate')}
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
