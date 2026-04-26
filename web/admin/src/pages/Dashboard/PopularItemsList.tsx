import { useTranslation } from 'react-i18next';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import type { PopularItem } from '@/api/admin-stats';

// START_MODULE_CONTRACT
//   PURPOSE: Render the dashboard "popular items" table with locale-aware name
//            picking. Pure presentation given a PopularItem[] from the parent.
//   SCOPE:   Used only by DashboardPage.
//   DEPENDS: react-i18next, @/components/ui/table, @/api/admin-stats type.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, INV-014 (snapshot names
//            from order_items keep this list stable across menu renames).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PopularItemsList - localized popular items table or empty state
// END_MODULE_MAP

interface PopularItemsListProps {
  items: PopularItem[];
  locale: 'ru' | 'en';
}

function pickName(item: PopularItem, locale: 'ru' | 'en'): string {
  if (locale === 'ru') return item.name_ru || item.name_en;
  return item.name_en || item.name_ru;
}

export function PopularItemsList({ items, locale }: PopularItemsListProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3" data-testid="popular-items-list">
      <h2 className="text-lg font-semibold">{t('pages.dashboard.popular.title')}</h2>
      {items.length === 0 ? (
        <p className="text-muted-foreground text-sm py-4" data-testid="popular-items-empty">
          {t('pages.dashboard.popular.empty')}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('pages.dashboard.popular.column.name')}</TableHead>
              <TableHead>{t('pages.dashboard.popular.column.quantity')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, idx) => (
              <TableRow key={`${item.name_ru}|${item.name_en}|${idx}`} data-testid="popular-items-row">
                <TableCell>{pickName(item, locale)}</TableCell>
                <TableCell>{item.quantity}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
