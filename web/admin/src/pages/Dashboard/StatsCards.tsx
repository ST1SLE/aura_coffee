import { useTranslation } from 'react-i18next';
import { formatKopecks } from '@/lib/money';

// START_MODULE_CONTRACT
//   PURPOSE: Two summary cards — revenue (formatted via formatKopecks) and
//            orders count (locale-formatted integer). Pure presentation.
//   SCOPE:   Used only by DashboardPage.
//   DEPENDS: react-i18next, @/lib/money.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §5.2.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   StatsCards - revenue + orders summary cards
// END_MODULE_MAP

interface StatsCardsProps {
  revenueKopecks: number;
  ordersCount: number;
  locale: 'ru' | 'en';
}

export function StatsCards({ revenueKopecks, ordersCount, locale }: StatsCardsProps) {
  const { t } = useTranslation();
  const revenue = formatKopecks(revenueKopecks, locale);
  const count = new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US').format(ordersCount);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div
        className="rounded-lg border bg-card p-6 shadow-sm"
        data-testid="stats-card-revenue"
      >
        <p className="text-sm text-muted-foreground">{t('pages.dashboard.cards.revenue')}</p>
        <p className="mt-2 text-3xl font-semibold">{revenue}</p>
      </div>
      <div
        className="rounded-lg border bg-card p-6 shadow-sm"
        data-testid="stats-card-orders"
      >
        <p className="text-sm text-muted-foreground">{t('pages.dashboard.cards.orders')}</p>
        <p className="mt-2 text-3xl font-semibold">{count}</p>
      </div>
    </div>
  );
}
