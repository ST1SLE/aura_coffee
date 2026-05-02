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
import type { PromocodeResponse, PromocodeState } from '@/api/promocodes';

// START_MODULE_CONTRACT
//   PURPOSE: Render the promocodes list as a clickable table with state chip,
//            formatted discount/uses/valid_until, and inline activate/deactivate
//            buttons gated by current state. Pure presentation given props.
//   SCOPE:   Used only by PromosPage.
//   DEPENDS: react-i18next, ui Table/Button/Badge, @/api/promocodes types.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PromosTable - clickable promo list with inline activate/deactivate
// END_MODULE_MAP

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

const mobileLabelClass =
  'text-xs font-medium uppercase tracking-wide text-muted-foreground md:hidden';
const responsiveRowClass =
  'block rounded-lg border bg-card p-3 shadow-sm md:table-row md:rounded-none md:border-b md:bg-transparent md:p-0 md:shadow-none';
const responsiveCellClass =
  'flex items-center justify-between gap-4 py-2 text-sm md:table-cell md:p-2';

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
          <TableHead>{t('pages.promos.columns.code')}</TableHead>
          <TableHead>{t('pages.promos.columns.state')}</TableHead>
          <TableHead>{t('pages.promos.columns.discount')}</TableHead>
          <TableHead>{t('pages.promos.columns.valid_until')}</TableHead>
          <TableHead>{t('pages.promos.columns.uses')}</TableHead>
          <TableHead className="text-right">
            {t('pages.promos.columns.actions')}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody className="block space-y-3 md:table-row-group md:space-y-0">
        {items.map((promo) => {
          const isPending = pendingId === promo.id;
          const canActivate = promo.state === 'inactive';
          const canDeactivate = promo.state === 'active';
          const validUntilClass =
            promo.state === 'expired' ? 'text-muted-foreground' : '';
          return (
            <TableRow
              key={promo.id}
              className={`${responsiveRowClass} cursor-pointer`}
              onClick={() => onRowClick(promo)}
              data-testid={`promo-row-${promo.code}`}
            >
              <TableCell className={responsiveCellClass}>
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.code')}
                </span>
                <span className="font-mono">{promo.code}</span>
              </TableCell>
              <TableCell className={responsiveCellClass}>
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.state')}
                </span>
                <span>
                  <StateChip state={promo.state} />
                </span>
              </TableCell>
              <TableCell className={responsiveCellClass}>
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.discount')}
                </span>
                <span>{formatDiscount(promo)}</span>
              </TableCell>
              <TableCell
                className={`${responsiveCellClass} ${validUntilClass}`}
                data-testid={`valid-until-${promo.code}`}
              >
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.valid_until')}
                </span>
                <span className="text-right md:text-left">
                  {formatValidUntil(promo.valid_until)}
                </span>
              </TableCell>
              <TableCell className={responsiveCellClass}>
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.uses')}
                </span>
                <span>{formatUses(promo.current_uses, promo.max_uses)}</span>
              </TableCell>
              <TableCell
                className={`${responsiveCellClass} md:text-right`}
                onClick={(e) => e.stopPropagation()}
              >
                <span className={mobileLabelClass}>
                  {t('pages.promos.columns.actions')}
                </span>
                <div className="flex flex-wrap justify-end gap-2">
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
