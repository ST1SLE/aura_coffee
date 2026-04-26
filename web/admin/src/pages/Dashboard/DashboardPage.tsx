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

// START_MODULE_CONTRACT
//   PURPOSE: Admin dashboard — selects a time range (today/week/month) and
//            fetches /api/v1/admin/stats, then renders revenue/orders cards
//            and a popular items table.
//   SCOPE:   Index page of the admin layout (admin-only via DashboardIndex
//            redirect in App.tsx; baristas land on /orders).
//   DEPENDS: react, react-i18next, @/api/admin-stats, @/components/ui/notifier,
//            sibling Dashboard subcomponents.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §4.5/§7.1,
//            INV-002 (admin scope server-enforced), INV-014 (popular items use
//            snapshot names from order_items).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   DashboardPage - data-fetching index page with range tabs + stats + popular
// END_MODULE_MAP

// START_CONTRACT: DashboardPage
//   PURPOSE: Fetch admin dashboard stats whenever the selected range changes,
//            handle 401 silently (authenticatedFetch redirects), surface other
//            errors via notifier, and render range tabs + stats cards + popular
//            items list.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET /api/v1/admin/stats on mount and on range change;
//            notifier toasts for failures; cancellation flag avoids stale
//            setState after unmount.
//   LINKS:   INV-002 (server enforces admin scope; 403 would land here as a
//            generic "load failed" toast — UX, not security).
// END_CONTRACT: DashboardPage
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
