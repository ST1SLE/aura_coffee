import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bell, ChevronLeft, ReceiptText } from 'lucide-react';
import {
  listNotifications,
  type NotificationFeedItem,
} from '@/api/notifications';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: /profile/notifications route — read-only customer notification
//            feed over in-app notification rows.
//   SCOPE:   NotificationsPage component.
//   DEPENDS: react, react-router-dom, react-i18next, lucide-react,
//            @/api/notifications, @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5.2;
//            INV-013 (customer sees only own feed rows from core-api).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   NotificationsPage - profile notification feed with load-more pagination
// END_MODULE_MAP

const PER_PAGE = 20;

function formatDate(iso: string, locale: string): string {
  try {
    return new Date(iso).toLocaleString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

function messageFor(notification: NotificationFeedItem, lang: 'ru' | 'en'): string {
  return lang === 'ru' ? notification.message_ru : notification.message_en;
}

// START_CONTRACT: NotificationsPage
//   PURPOSE: Fetch and render the customer's in-app notification feed with
//            localized text, order links, empty/loading/error states, and
//            load-more pagination.
//   INPUTS:  none.
//   OUTPUTS: JSX.
//   SIDE_EFFECTS: HTTP listNotifications(page, PER_PAGE) on mount/page change.
//                 No client-side notification mutation or read-state tracking.
//   LINKS:   PDD §5.2, INV-002, INV-013.
// END_CONTRACT: NotificationsPage
export function NotificationsPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru-RU' : 'en-US';
  const [items, setItems] = useState<NotificationFeedItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listNotifications(page, PER_PAGE)
      .then((body) => {
        if (cancelled) return;
        setTotalCount(body.total_count);
        setItems((prev) =>
          body.page === 1 ? body.notifications : [...prev, ...body.notifications],
        );
      })
      .catch(() => {
        if (!cancelled) setError(t('pages.notifications.loadError'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [page, t]);

  const hasMore = useMemo(
    () => items.length < totalCount,
    [items.length, totalCount],
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-5 md:px-6">
      <Button asChild variant="ghost" className="pl-0">
        <Link to="/profile">
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          {t('pages.notifications.backToProfile')}
        </Link>
      </Button>

      <div className="aura-surface flex items-start gap-3 rounded-lg bg-card/95 p-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-primary/25 bg-primary text-primary-foreground shadow-[0_10px_24px_rgba(27,23,19,0.16)]">
          <Bell className="h-6 w-6" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-semibold tracking-normal">
            {t('pages.notifications.title')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('pages.notifications.description')}
          </p>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      {loading && items.length === 0 && (
        <div className="aura-surface rounded-lg p-4" role="status">
          {t('pages.notifications.loading')}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="aura-surface flex min-h-[35vh] flex-col items-center justify-center rounded-lg p-6 text-center">
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand-sage text-brand-sage-foreground">
            <Bell className="h-6 w-6" aria-hidden="true" />
          </span>
          <h2 className="font-display text-xl font-semibold">
            {t('pages.notifications.emptyTitle')}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t('pages.notifications.emptyDescription')}
          </p>
        </div>
      )}

      {items.length > 0 && (
        <section className="space-y-3" aria-label={t('pages.notifications.title')}>
          {items.map((notification) => (
            <article
              key={notification.id}
              className="aura-surface flex gap-3 rounded-lg bg-card/95 p-4"
            >
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-primary">
                <Bell className="h-4 w-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {messageFor(notification, lang)}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatDate(notification.created_at, locale)}</span>
                  {notification.order_id && (
                    <Link
                      to={`/orders/${notification.order_id}`}
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <ReceiptText className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('pages.notifications.orderLink', {
                        id: shortId(notification.order_id),
                      })}
                    </Link>
                  )}
                </div>
              </div>
            </article>
          ))}
        </section>
      )}

      {items.length > 0 && hasMore && (
        <Button
          type="button"
          variant="secondary"
          disabled={loading}
          onClick={() => setPage((current) => current + 1)}
        >
          {loading
            ? t('pages.notifications.loading')
            : t('pages.notifications.loadMore')}
        </Button>
      )}
    </div>
  );
}
