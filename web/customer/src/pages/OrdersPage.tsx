import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, ReceiptText, RotateCcw } from 'lucide-react';
import {
  listOrders,
  repeatOrder,
  OrderApiError,
  type OrderItemResponse,
  type OrderResponse,
} from '@/api/orders';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';

// START_MODULE_CONTRACT
//   PURPOSE: Customer order history route — fetches GET /api/v1/orders,
//            splits active vs historical orders, renders immutable item
//            snapshots and server-owned totals, and links each order to its
//            status/detail page.
//   SCOPE:   OrdersPage component.
//   DEPENDS: react, react-router-dom, react-i18next, lucide-react,
//            @/api/orders, @/components/ui/button, @/lib/formatPrice.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4, §7.7;
//            INV-014 (order_items are rendered as immutable snapshots).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrdersPage  - /orders history with active/history sections
// END_MODULE_MAP

const ACTIVE_STATUSES = new Set([
  'created',
  'paid',
  'preparing',
  'ready',
  'in_delivery',
]);

function shortId(id: string): string {
  return id.slice(0, 8);
}

function itemName(item: OrderItemResponse, lang: 'ru' | 'en'): string {
  return lang === 'ru' ? item.menu_item_name_ru : item.menu_item_name_en;
}

function renderModifiers(item: OrderItemResponse, lang: 'ru' | 'en'): string {
  return item.modifiers_snapshot
    .map((raw) => {
      const modifier = raw as {
        name_ru?: string;
        name_en?: string;
        name?: string;
        label?: string;
      };
      return lang === 'ru'
        ? (modifier.name_ru ?? modifier.name ?? modifier.label ?? '')
        : (modifier.name_en ?? modifier.name ?? modifier.label ?? '');
    })
    .filter(Boolean)
    .join(', ');
}

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

function renderError(err: unknown, fallback: string): string {
  if (err instanceof OrderApiError && err.detail) return err.detail;
  return fallback;
}

interface OrderCardProps {
  order: OrderResponse;
  lang: 'ru' | 'en';
  locale: string;
  onRepeat: (orderId: string) => void;
  repeating: boolean;
}

function OrderCard({
  order,
  lang,
  locale,
  onRepeat,
  repeating,
}: OrderCardProps) {
  const { t } = useTranslation();
  const previewItems = order.items.slice(0, 3);

  return (
    <article className="aura-surface flex flex-col gap-4 rounded-lg p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">
              {t('pages.orders.orderNumber', { id: shortId(order.id) })}
            </h2>
            <span className="rounded-full bg-secondary px-2 py-1 text-xs font-medium text-secondary-foreground">
              {t(`pages.orders.status.${order.status}`)}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatDate(order.created_at, locale)} ·{' '}
            {t(`pages.orders.type.${order.type}`)}
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-sm text-muted-foreground">
            {t('pages.orders.total')}
          </p>
          <p className="text-xl font-semibold text-primary">
            {formatPrice(order.total, locale)}
          </p>
        </div>
      </div>

      <ul className="space-y-2">
        {previewItems.map((item, index) => {
          const modifiers = renderModifiers(item, lang);
          return (
            <li
              key={item.id ?? `${order.id}-${index}`}
              className="flex justify-between gap-3 text-sm"
            >
              <span className="min-w-0">
                <span className="font-medium">{itemName(item, lang)}</span>
                {item.size_label && (
                  <span className="text-muted-foreground">
                    {' '}
                    · {item.size_label}
                  </span>
                )}
                {modifiers && (
                  <span className="block text-xs text-muted-foreground">
                    {modifiers}
                  </span>
                )}
              </span>
              <span className="shrink-0 text-muted-foreground">
                {item.quantity} × {formatPrice(item.unit_price, locale)}
              </span>
            </li>
          );
        })}
        {order.items.length > previewItems.length && (
          <li className="text-xs text-muted-foreground">
            {t('pages.orders.moreItems', {
              count: order.items.length - previewItems.length,
            })}
          </li>
        )}
      </ul>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild className="sm:w-auto">
          <Link to={`/orders/${order.id}`}>
            {t('pages.orders.details')}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onRepeat(order.id)}
          disabled={repeating}
          className="sm:w-auto"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t('pages.orders.repeat')}
        </Button>
      </div>
    </article>
  );
}

// START_CONTRACT: OrdersPage
//   PURPOSE: Fetch and render the customer's real order history, preserving
//            backend response ownership for item snapshots and totals.
//   INPUTS:  none.
//   OUTPUTS: JSX — loading/error/empty or active/history order lists.
//   SIDE_EFFECTS: HTTP listOrders() on mount; optional repeatOrder() action
//                 then navigate('/cart'). No client-side pricing calculations.
//   LINKS:   PDD §4.4, §7.7, INV-014.
// END_CONTRACT: OrdersPage
export function OrdersPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru-RU' : 'en-US';

  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [repeatingId, setRepeatingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listOrders(page, perPage)
      .then((body) => {
        if (cancelled) return;
        setOrders(body.orders);
        setPage(body.page);
        setPerPage(body.per_page);
        setTotalCount(body.total_count);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(renderError(err, t('pages.orders.loadError')));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [page, perPage, t]);

  const activeOrders = useMemo(
    () => orders.filter((order) => ACTIVE_STATUSES.has(order.status)),
    [orders],
  );
  const historyOrders = useMemo(
    () => orders.filter((order) => !ACTIVE_STATUSES.has(order.status)),
    [orders],
  );
  const hasNextPage = page * perPage < totalCount;

  async function handleRepeat(orderId: string) {
    setRepeatingId(orderId);
    setError(null);
    try {
      const result = await repeatOrder(orderId);
      if (result.skipped.length > 0) {
        navigate('/cart', { state: { repeatOrderSkipped: result.skipped } });
      } else {
        navigate('/cart');
      }
    } catch (err) {
      setError(renderError(err, t('pages.orders.repeatError')));
    } finally {
      setRepeatingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-5 md:px-6">
      <div className="aura-surface rounded-lg p-4">
        <h1 className="text-3xl font-semibold tracking-normal">
          {t('pages.orders.title')}
        </h1>
        <p className="mt-2 text-muted-foreground">
          {t('pages.orders.description')}
        </p>
      </div>

      {loading && (
        <div className="aura-surface rounded-lg p-4" role="status">
          {t('pages.orders.loading')}
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      {!loading && !error && orders.length === 0 && (
        <div className="aura-surface flex min-h-[35vh] flex-col items-center justify-center rounded-lg p-6 text-center">
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-primary">
            <ReceiptText className="h-6 w-6" aria-hidden="true" />
          </span>
          <h2 className="text-xl font-semibold">
            {t('pages.orders.emptyTitle')}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t('pages.orders.emptyDescription')}
          </p>
          <Button asChild className="mt-4">
            <Link to="/menu">{t('cart.emptyCta')}</Link>
          </Button>
        </div>
      )}

      {!loading && activeOrders.length > 0 && (
        <section className="space-y-3" aria-labelledby="active-orders-heading">
          <h2 id="active-orders-heading" className="text-xl font-semibold">
            {t('pages.orders.activeTitle')}
          </h2>
          {activeOrders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              lang={lang}
              locale={locale}
              onRepeat={handleRepeat}
              repeating={repeatingId === order.id}
            />
          ))}
        </section>
      )}

      {!loading && historyOrders.length > 0 && (
        <section className="space-y-3" aria-labelledby="history-orders-heading">
          <h2 id="history-orders-heading" className="text-xl font-semibold">
            {t('pages.orders.historyTitle')}
          </h2>
          {historyOrders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              lang={lang}
              locale={locale}
              onRepeat={handleRepeat}
              repeating={repeatingId === order.id}
            />
          ))}
        </section>
      )}

      {!loading && orders.length > 0 && hasNextPage && (
        <Button
          type="button"
          variant="secondary"
          onClick={() => setPage((current) => current + 1)}
        >
          {t('pages.orders.nextPage')}
        </Button>
      )}
    </div>
  );
}
