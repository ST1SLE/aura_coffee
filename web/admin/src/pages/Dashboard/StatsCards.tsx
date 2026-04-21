import { useTranslation } from 'react-i18next';
import { formatKopecks } from '@/lib/money';

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
