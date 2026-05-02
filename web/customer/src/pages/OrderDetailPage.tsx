import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  Check,
  Clock,
  CreditCard,
  RotateCcw,
  XCircle,
} from 'lucide-react';
import {
  cancelOrder,
  getOrder,
  repeatOrder,
  OrderApiError,
  type OrderItemResponse,
  type OrderResponse,
  type OrderStatus,
} from '@/api/orders';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';
import { cn } from '@/lib/utils';

// START_MODULE_CONTRACT
//   PURPOSE: Customer order detail/status route — renders server-owned order
//            totals/items/status, polls for payment confirmation_url while
//            CREATED, redirects to payment when provided, then refreshes status
//            within PDD §4.4's 10s freshness window.
//   SCOPE:   OrderDetailPage component.
//   DEPENDS: react, react-router-dom, react-i18next, lucide-react,
//            @/api/orders, @/components/ui/button, @/lib/formatPrice, @/lib/utils.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4, §6.1, §7.6,
//            §7.7; INV-005, INV-014.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrderDetailPage  - /orders/:orderId status, payment handoff, receipt
// END_MODULE_MAP

const CREATED_POLL_MS = 1500;
const STATUS_POLL_MS = 10_000;
const TERMINAL_STATUSES = new Set<OrderStatus>(['completed', 'cancelled']);
const TIMELINE: OrderStatus[] = [
  'created',
  'paid',
  'preparing',
  'ready',
  'in_delivery',
  'completed',
];

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

function formatDate(
  iso: string | null | undefined,
  locale: string,
): string | null {
  if (!iso) return null;
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

function isLocalFakeYukassaUrl(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin);
    const isLocalHost =
      parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
    return (
      isLocalHost && parsed.pathname.startsWith('/dev/yukassa-sandbox/')
    );
  } catch {
    return false;
  }
}

interface StatusTimelineProps {
  status: OrderStatus;
}

function StatusTimeline({ status }: StatusTimelineProps) {
  const { t } = useTranslation();
  const currentIndex = TIMELINE.indexOf(status);
  const cancelled = status === 'cancelled';

  return (
    <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {TIMELINE.map((step, index) => {
        const reached = !cancelled && index <= currentIndex;
        return (
          <li
            key={step}
            className={cn(
              'flex min-h-20 flex-col justify-between rounded-md border px-3 py-2 text-sm',
              reached
                ? 'border-primary/40 bg-primary/10 text-foreground'
                : 'border-white/10 bg-background/50 text-muted-foreground',
            )}
          >
            <span>{t(`pages.orders.status.${step}`)}</span>
            {reached ? (
              <Check className="h-4 w-4 text-primary" aria-hidden="true" />
            ) : (
              <Clock className="h-4 w-4" aria-hidden="true" />
            )}
          </li>
        );
      })}
      {cancelled && (
        <li className="flex min-h-20 flex-col justify-between rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <span>{t('pages.orders.status.cancelled')}</span>
          <XCircle className="h-4 w-4" aria-hidden="true" />
        </li>
      )}
    </ol>
  );
}

interface ReceiptProps {
  order: OrderResponse;
  lang: 'ru' | 'en';
  locale: string;
}

function Receipt({ order, lang, locale }: ReceiptProps) {
  const { t } = useTranslation();

  return (
    <div className="aura-surface space-y-4 rounded-lg p-4">
      <h2 className="text-xl font-semibold">{t('pages.orders.receipt')}</h2>
      <ul className="space-y-3">
        {order.items.map((item, index) => {
          const modifiers = renderModifiers(item, lang);
          return (
            <li
              key={item.id ?? `${order.id}-${index}`}
              className="rounded-md border border-white/10 bg-background/50 p-3"
            >
              <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{itemName(item, lang)}</p>
                  {item.size_label && (
                    <p className="text-xs text-muted-foreground">
                      {item.size_label}
                    </p>
                  )}
                  {modifiers && (
                    <p className="text-xs text-muted-foreground">{modifiers}</p>
                  )}
                </div>
                <p className="shrink-0 text-sm text-muted-foreground">
                  {item.quantity} × {formatPrice(item.unit_price, locale)}
                </p>
              </div>
              <p className="mt-2 text-right font-semibold text-primary">
                {formatPrice(item.line_total, locale)}
              </p>
            </li>
          );
        })}
      </ul>
      <dl className="space-y-2 border-t border-white/10 pt-4 text-sm">
        <div className="flex justify-between gap-3">
          <dt>{t('pages.orders.subtotal')}</dt>
          <dd>{formatPrice(order.subtotal, locale)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t('pages.orders.discount')}</dt>
          <dd>{formatPrice(order.discount_amount, locale)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t('pages.orders.pointsUsed')}</dt>
          <dd>{order.points_used ?? 0}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{t('pages.orders.deliveryFee')}</dt>
          <dd>{formatPrice(order.delivery_fee, locale)}</dd>
        </div>
        <div className="flex justify-between gap-3 text-lg font-semibold">
          <dt>{t('pages.orders.total')}</dt>
          <dd className="text-primary">{formatPrice(order.total, locale)}</dd>
        </div>
      </dl>
    </div>
  );
}

// START_CONTRACT: OrderDetailPage
//   PURPOSE: Render one order's status, payment handoff, allowed actions, and
//            immutable receipt.
//   INPUTS:  none directly; reads :orderId from React Router params.
//   OUTPUTS: JSX — loading/error/not-found or order detail.
//   SIDE_EFFECTS: HTTP getOrder polling; window.location.assign() when backend
//                 provides an external confirmation_url for created. Local
//                 fake YuKassa sandbox URLs are not navigated to; the page keeps
//                 polling for the fake webhook. cancelOrder() only when UI
//                 state is paid; repeatOrder() then navigate('/cart'). No
//                 client-side price calculation.
//   LINKS:   PDD §4.4, §6.1, §7.6, §7.7; INV-005, INV-014.
// END_CONTRACT: OrderDetailPage
export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru-RU' : 'en-US';

  const [order, setOrder] = useState<OrderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [repeating, setRepeating] = useState(false);
  const [redirectedUrl, setRedirectedUrl] = useState<string | null>(null);

  const isTerminal = order ? TERMINAL_STATUSES.has(order.status) : false;
  const pollMs = order?.status === 'created' ? CREATED_POLL_MS : STATUS_POLL_MS;

  useEffect(() => {
    if (!orderId) {
      setLoading(false);
      setError(t('pages.orders.notFound'));
      return;
    }

    const currentOrderId = orderId;
    let cancelled = false;

    async function load(showLoading: boolean) {
      if (showLoading) setLoading(true);
      try {
        const next = await getOrder(currentOrderId);
        if (cancelled) return;
        setOrder(next);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(renderError(err, t('pages.orders.detailLoadError')));
        }
      } finally {
        if (!cancelled && showLoading) setLoading(false);
      }
    }

    void load(true);
    return () => {
      cancelled = true;
    };
  }, [orderId, t]);

  useEffect(() => {
    if (!orderId || !order || isTerminal) return;
    const timer = window.setInterval(() => {
      getOrder(orderId)
        .then((next) => {
          setOrder(next);
          setError(null);
        })
        .catch((err) => {
          setError(renderError(err, t('pages.orders.detailLoadError')));
        });
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [orderId, order, pollMs, isTerminal, t]);

  useEffect(() => {
    if (
      order?.status === 'created' &&
      order.confirmation_url &&
      !isLocalFakeYukassaUrl(order.confirmation_url) &&
      redirectedUrl !== order.confirmation_url
    ) {
      setRedirectedUrl(order.confirmation_url);
      window.location.assign(order.confirmation_url);
    }
  }, [order, redirectedUrl]);

  const createdAt = useMemo(
    () => formatDate(order?.created_at, locale),
    [order?.created_at, locale],
  );
  const readyAt = useMemo(
    () => formatDate(order?.estimated_ready_at, locale),
    [order?.estimated_ready_at, locale],
  );

  async function handleCancel() {
    if (!order) return;
    setCancelling(true);
    setActionError(null);
    try {
      setOrder(await cancelOrder(order.id));
    } catch (err) {
      setActionError(renderError(err, t('pages.orders.cancelError')));
    } finally {
      setCancelling(false);
    }
  }

  async function handleRepeat() {
    if (!order) return;
    setRepeating(true);
    setActionError(null);
    try {
      const result = await repeatOrder(order.id);
      if (result.skipped.length > 0) {
        navigate('/cart', { state: { repeatOrderSkipped: result.skipped } });
      } else {
        navigate('/cart');
      }
    } catch (err) {
      setActionError(renderError(err, t('pages.orders.repeatError')));
    } finally {
      setRepeating(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-5 md:px-6">
        <div className="aura-surface rounded-lg p-4" role="status">
          {t('pages.orders.detailLoading')}
        </div>
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-5 md:px-6">
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
        <Button asChild variant="secondary">
          <Link to="/orders">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            {t('pages.orders.backToOrders')}
          </Link>
        </Button>
      </div>
    );
  }

  if (!order) return null;

  const canCancel = order.status === 'paid';
  const isZeroTotalPaid = order.status === 'paid' && order.total === 0;

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-5 md:px-6">
      <Button asChild variant="ghost" className="px-0">
        <Link to="/orders">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t('pages.orders.backToOrders')}
        </Link>
      </Button>

      <section className="aura-surface space-y-4 rounded-lg p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">
              {t('pages.orders.orderNumber', { id: shortId(order.id) })}
            </h1>
            {createdAt && (
              <p className="text-sm text-muted-foreground">{createdAt}</p>
            )}
          </div>
          <span className="w-fit rounded-full bg-secondary px-3 py-1 text-sm font-medium text-secondary-foreground">
            {t(`pages.orders.status.${order.status}`)}
          </span>
        </div>

        <StatusTimeline status={order.status} />

        {order.status === 'created' && !order.confirmation_url && (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
            {t('pages.orders.paymentWaiting')}
          </p>
        )}
        {order.status === 'created' && order.confirmation_url && (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
            <CreditCard className="mr-2 inline h-4 w-4" aria-hidden="true" />
            {t('pages.orders.paymentRedirecting')}
          </p>
        )}
        {isZeroTotalPaid && (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
            {t('pages.orders.zeroTotalPaid')}
          </p>
        )}
        {readyAt && (
          <p className="text-sm text-muted-foreground">
            {t('pages.orders.estimatedReadyAt', { value: readyAt })}
          </p>
        )}
      </section>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}
      {actionError && (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {actionError}
        </p>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        {canCancel && (
          <Button
            type="button"
            variant="destructive"
            onClick={handleCancel}
            disabled={cancelling}
          >
            {t('pages.orders.cancel')}
          </Button>
        )}
        <Button
          type="button"
          variant="secondary"
          onClick={handleRepeat}
          disabled={repeating}
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t('pages.orders.repeat')}
        </Button>
      </div>

      <Receipt order={order} lang={lang} locale={locale} />
    </div>
  );
}
