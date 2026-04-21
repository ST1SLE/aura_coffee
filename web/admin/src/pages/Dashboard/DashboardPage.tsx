import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import {
  getAdminStats,
  ApiError,
} from '@/api/admin-stats';
import type { AdminStatsResponse, StatsRange } from '@/api/admin-stats';
import { RangeSelector } from './RangeSelector';
import { StatsCards } from './StatsCards';
import { PopularItemsList } from './PopularItemsList';

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const locale: 'ru' | 'en' = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const { notifications, notify, dismiss } = useNotifier();

  const [range, setRange] = useState<StatsRange>('month');
  const [data, setData] = useState<AdminStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAdminStats(range)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          // 401 уже обработан в authenticatedFetch (редирект на /login).
          return;
        }
        notify(t('pages.dashboard.errors.loadFailed'), 'error');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range]);

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div>
        <h1 className="text-2xl font-bold">{t('pages.dashboard.title')}</h1>
        <p className="mt-2 text-muted-foreground">{t('pages.dashboard.description')}</p>
      </div>

      <RangeSelector value={range} onChange={setRange} />

      {loading && data === null ? (
        <p className="text-muted-foreground text-sm py-8 text-center">{t('common.loading')}</p>
      ) : data ? (
        <>
          <StatsCards
            revenueKopecks={data.revenue_kopecks}
            ordersCount={data.orders_count}
            locale={locale}
          />
          <PopularItemsList items={data.popular_items} locale={locale} />
        </>
      ) : null}

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
