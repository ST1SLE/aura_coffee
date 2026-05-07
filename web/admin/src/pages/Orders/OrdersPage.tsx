import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { NotificationList, useNotifier } from '@/components/ui/notifier';
import { listAdminOrders, getAdminOrder, ApiError } from '@/api/admin-orders';
import { useCurrentRole } from '@/lib/auth';
import type {
  OrderResponse,
  OrderStatus,
  OrderType,
  AdminOrderStatusFilter,
  OrderListResponse,
  StaffOrderDetailResponse,
} from '@/api/admin-orders';
import { OrdersTable } from './OrdersTable';
import { OrderDetailDialog } from './OrderDetailDialog';

// START_MODULE_CONTRACT
//   PURPOSE: Admin/barista orders feed — status filter tabs (incl. 'active'
//            aggregate), type filter, paginated list, polling on 'active' tab
//            (paused when document.hidden), and an OrderDetailDialog for
//            inspecting, contacting, transitioning orders, and retrying failed
//            refunds.
//   SCOPE:   Mounted at /orders under the admin/barista layout. Visible to both
//            roles; the dialog hides destructive controls for non-admin roles.
//   DEPENDS: react, react-router-dom, react-i18next, ui primitives,
//            @/api/admin-orders, sibling OrdersTable + OrderDetailDialog.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.1 order state machine,
//            PDD §6.2 payment refund retry,
//            AGENTS.md (real-time feed within 5s — implemented as 5s polling),
//            INV-002 (server enforces role on every transition),
//            INV-013 (contact phone appears only after staff detail fetch),
//            INV-014 (order_items shown carry snapshot names),
//            INV-016 (state-machine transitions triggered from the detail dialog).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrdersPage - data-fetching admin/barista orders feed with poll + filters
// END_MODULE_MAP

// Таб-сет — серверный фильтр status. 'active' — агрегирующий
// (created+paid+preparing+ready+in_delivery), 'refund_failed' —
// exception queue по платежу.
const STATUS_TABS: AdminOrderStatusFilter[] = [
  'active',
  'refund_failed',
  'paid',
  'preparing',
  'ready',
  'in_delivery',
  'completed',
  'cancelled',
];

const TYPE_OPTIONS: Array<OrderType | 'all'> = ['all', 'pickup', 'delivery'];

const PER_PAGE = 20;
const POLL_INTERVAL_MS = 5_000;

// Нормализация query-string значений: кривой URL не должен крашить страницу.
function parseStatus(raw: string | null): AdminOrderStatusFilter {
  if (!raw) return 'active';
  const all: AdminOrderStatusFilter[] = [
    'active',
    'created',
    'paid',
    'preparing',
    'ready',
    'in_delivery',
    'completed',
    'cancelled',
    'refund_failed',
  ];
  return (all as string[]).includes(raw)
    ? (raw as AdminOrderStatusFilter)
    : 'active';
}

function parseType(raw: string | null): OrderType | 'all' {
  if (raw === 'pickup' || raw === 'delivery') return raw;
  return 'all';
}

function isApiErrorDetail(body: unknown, detail: string): boolean {
  return (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    (body as { detail?: unknown }).detail === detail
  );
}

function parsePage(raw: string | null): number {
  const n = raw ? Number.parseInt(raw, 10) : 1;
  return Number.isFinite(n) && n > 0 ? n : 1;
}

// START_CONTRACT: OrdersPage
//   PURPOSE: Sync filter state with URL query params, fetch the paginated order
//            list, poll the 'active' filter every 5s while the tab is visible,
//            and own the selected-order dialog with retry-after-error logic.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: GET listAdminOrders / getAdminOrder; polling interval lifecycle;
//            visibilitychange listener; URL search param updates; transition
//            actions are dispatched from the dialog and refresh both the list
//            and the open order on success.
//   LINKS:   INV-002 (admin and barista may read; the underlying transition
//            endpoints accept role-specific actions — server is authoritative),
//            INV-016 (transitions go through the dialog).
// END_CONTRACT: OrdersPage
export function OrdersPage() {
  const { t } = useTranslation();
  const { notifications, notify, dismiss } = useNotifier();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentRole = useCurrentRole();

  const requestedStatus = parseStatus(searchParams.get('status'));
  const canViewRefundIssues = currentRole === 'admin';
  const status =
    requestedStatus === 'refund_failed' && !canViewRefundIssues
      ? 'active'
      : requestedStatus;
  const type = parseType(searchParams.get('type'));
  const page = parsePage(searchParams.get('page'));

  const [rows, setRows] = useState<OrderResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedOrder, setSelectedOrder] =
    useState<StaffOrderDetailResponse | null>(null);

  // Последний reload-call должен выигрывать гонку с запоздалым предыдущим.
  const reqSeq = useRef(0);

  const setFilter = useCallback(
    (patch: {
      status?: AdminOrderStatusFilter;
      type?: OrderType | 'all';
      page?: number;
    }) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        // Смена любого фильтра (status/type) → page сбрасывается на 1, если
        // caller не задал page явно.
        const resetPage =
          (patch.status !== undefined || patch.type !== undefined) &&
          patch.page === undefined;
        if (patch.status !== undefined) {
          if (patch.status === 'active') next.delete('status');
          else next.set('status', patch.status);
        }
        if (patch.type !== undefined) {
          if (patch.type === 'all') next.delete('type');
          else next.set('type', patch.type);
        }
        if (patch.page !== undefined) {
          if (patch.page <= 1) next.delete('page');
          else next.set('page', String(patch.page));
        } else if (resetPage) {
          next.delete('page');
        }
        return next;
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (requestedStatus === status) return;
    setFilter({ status });
  }, [requestedStatus, status, setFilter]);

  // Классификация ошибок — единая точка принятия решений (spec: "Error handling").
  const handleApiError = useCallback(
    async (err: unknown, ctx: { orderId?: string } = {}) => {
      if (!(err instanceof ApiError)) {
        notify(t('common.error'), 'error');
        return;
      }
      switch (err.status) {
        case 401:
          notify(t('common.sessionExpired'), 'error');
          return;
        case 403:
          notify(t('pages.orders.errors.forbidden'), 'error');
          return;
        case 404:
          notify(t('pages.orders.errors.not_found'), 'error');
          setSelectedId(null);
          setSelectedOrder(null);
          // refetch списка
          reload();
          return;
        case 409:
          notify(
            isApiErrorDetail(err.body, 'refund_not_retryable')
              ? t('pages.orders.errors.refund_retry_not_allowed')
              : t('pages.orders.errors.illegal_transition'),
            'error',
          );
          if (ctx.orderId) {
            try {
              const fresh = await getAdminOrder(ctx.orderId);
              setSelectedOrder(fresh);
              setRows((prev) =>
                prev.map((r) => (r.id === fresh.id ? fresh : r)),
              );
            } catch {
              /* вторичная ошибка — не каскадируем */
            }
          }
          return;
        default:
          notify(t('common.error'), 'error');
      }
    },
    // reload добавлен через ref-паттерн ниже (замыкание через функциональный update).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, notify],
  );

  const reload = useCallback(async () => {
    const seq = ++reqSeq.current;
    setLoading(true);
    try {
      const params: Parameters<typeof listAdminOrders>[0] = {
        status,
        page,
        per_page: PER_PAGE,
      };
      if (type !== 'all') params.type = type;
      const res: OrderListResponse = await listAdminOrders(params);
      if (seq !== reqSeq.current) return; // устаревший ответ
      setRows(res.orders);
      setTotalCount(res.total_count);
    } catch (err) {
      if (seq !== reqSeq.current) return;
      handleApiError(err);
    } finally {
      if (seq === reqSeq.current) setLoading(false);
    }
  }, [status, type, page, handleApiError]);

  // Первый рендер + смена любого фильтра → новый запрос.
  useEffect(() => {
    reload();
  }, [reload]);

  // Поллинг: только на `active` и только когда вкладка видима.
  // Пауза на visibilitychange=hidden, возобновление на visible.
  useEffect(() => {
    if (status !== 'active') return;
    if (typeof document === 'undefined') return;

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (intervalId != null) return;
      intervalId = setInterval(() => {
        reload();
      }, POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (intervalId == null) return;
      clearInterval(intervalId);
      intervalId = null;
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') start();
      else stop();
    };

    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [status, reload]);

  // При выборе строки подгружаем детальный order (payload идентичен list-элементу,
  // но через GET /admin/orders/{id} мы гарантируем свежее состояние после action).
  useEffect(() => {
    if (!selectedId) {
      setSelectedOrder(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const fresh = await getAdminOrder(selectedId);
        if (!cancelled) setSelectedOrder(fresh);
      } catch (err) {
        if (!cancelled) {
          handleApiError(err, { orderId: selectedId });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, handleApiError]);

  const totalPages = Math.max(1, Math.ceil(totalCount / PER_PAGE));
  const visibleStatusTabs = STATUS_TABS.filter(
    (s) => s !== 'refund_failed' || canViewRefundIssues,
  );

  function labelForStatusTab(s: AdminOrderStatusFilter): string {
    if (s === 'active') return t('pages.orders.filters.active');
    if (s === 'all') return t('pages.orders.filters.type_all');
    if (s === 'refund_failed') return t('pages.orders.filters.refund_failed');
    return t(`pages.orders.status.${s as OrderStatus}`);
  }

  function labelForTypeOption(o: OrderType | 'all'): string {
    if (o === 'all') return t('pages.orders.filters.type_all');
    if (o === 'pickup') return t('pages.orders.filters.type_pickup');
    return t('pages.orders.filters.type_delivery');
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{t('pages.orders.title')}</h1>
          <p className="text-muted-foreground text-sm">
            {t('pages.orders.description')}
          </p>
        </div>
      </div>

      <div className="admin-surface-soft space-y-4 p-4">
        <div className="flex flex-wrap gap-2" role="tablist">
          {visibleStatusTabs.map((s) => (
            <Button
              key={s}
              role="tab"
              variant={status === s ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter({ status: s })}
              data-testid={`orders-tab-${s}`}
              aria-selected={status === s}
            >
              {labelForStatusTab(s)}
            </Button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <label
            htmlFor="orders-type-filter"
            className="text-sm font-medium text-foreground/75"
          >
            {t('pages.orders.filters.type')}
          </label>
          <select
            id="orders-type-filter"
            data-testid="orders-type-filter"
            className="h-9 rounded-md border border-input bg-[hsl(var(--field))] px-3 text-sm shadow-sm focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/25"
            value={type}
            onChange={(e) =>
              setFilter({ type: e.target.value as OrderType | 'all' })
            }
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {labelForTypeOption(o)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && rows.length === 0 ? (
        <p className="text-muted-foreground text-sm py-8 text-center">
          {t('common.loading')}
        </p>
      ) : (
        <OrdersTable
          rows={rows}
          onSelect={(id) => setSelectedId(id)}
          emptyLabel={t('pages.orders.empty')}
        />
      )}

      <div className="flex items-center justify-between">
        <span
          className="text-sm text-muted-foreground"
          data-testid="orders-page-indicator"
        >
          {t('pages.orders.pagination.page', { page })}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setFilter({ page: Math.max(1, page - 1) })}
            disabled={page <= 1}
            data-testid="orders-page-prev"
          >
            {t('pages.orders.pagination.previous')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setFilter({ page: page + 1 })}
            disabled={page >= totalPages}
            data-testid="orders-page-next"
          >
            {t('pages.orders.pagination.next')}
          </Button>
        </div>
      </div>

      <OrderDetailDialog
        order={selectedOrder}
        open={selectedId != null}
        onClose={() => setSelectedId(null)}
        onAction={async () => {
          // После успешного перехода — обновляем и список, и открытый order.
          await reload();
          if (selectedId) {
            try {
              const fresh = await getAdminOrder(selectedId);
              setSelectedOrder(fresh);
            } catch (err) {
              handleApiError(err, { orderId: selectedId });
            }
          }
        }}
        onError={(err) =>
          handleApiError(err, { orderId: selectedId ?? undefined })
        }
      />

      <NotificationList notifications={notifications} onDismiss={dismiss} />
    </div>
  );
}
