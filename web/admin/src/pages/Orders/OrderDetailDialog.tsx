import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Phone, RefreshCw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { StatusBadge } from './StatusBadge';
import { useCurrentRole } from '@/lib/auth';
import {
  updateOrderStatus,
  cancelAdminOrder,
  retryRefund,
  ApiError,
} from '@/api/admin-orders';
import type { OrderStatus, StaffOrderDetailResponse } from '@/api/admin-orders';

// START_MODULE_CONTRACT
//   PURPOSE: Modal dialog showing full order detail (items, totals, customer
//            contact/payment recovery state), and exposing role-gated
//            state-machine actions — Accept (paid→preparing), Mark Ready
//            (preparing→ready), Hand Out (ready→completed for pickup), Cancel
//            (admin only), Retry Refund (admin only).
//   SCOPE:   Mounted by OrdersPage with the currently selected order.
//   DEPENDS: react, react-i18next, ui primitives, @/lib/auth (useCurrentRole),
//            lucide-react, @/api/admin-orders, ./StatusBadge.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.1 order state machine,
//            INV-002 (server enforces role on every transition; client merely
//            decides which buttons to render),
//            INV-013 (customer_contact_phone is detail-only staff PII),
//            INV-014 (item names rendered from snapshot fields),
//            INV-016 (each button triggers an INV-016 state-machine transition).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrderDetailDialog - role-gated modal that renders order detail and dispatches transitions
// END_MODULE_MAP

// Форматируем копейки в "350,00 ₽" (locale ru-RU, currency RUB).
// Отрицательная скидка рендерится как "-50,00 ₽"; ноль — без минуса.
const moneyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
});

function formatKopecks(kopecks: number): string {
  return moneyFormatter.format(kopecks / 100);
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

interface OrderDetailDialogProps {
  order: StaffOrderDetailResponse | null;
  open: boolean;
  onClose: () => void;
  onAction: () => void;
  onError?: (error: unknown) => void;
}

interface StaffActionsProps {
  order: StaffOrderDetailResponse;
  onTransition: (next: OrderStatus) => Promise<void>;
  onCancelClick: () => void;
  onRefundRetry: () => Promise<void>;
  inFlight: boolean;
}

function StaffActions({
  order,
  onTransition,
  onCancelClick,
  onRefundRetry,
  inFlight,
}: StaffActionsProps) {
  const { t } = useTranslation();
  const role = useCurrentRole();

  // Таблица ролей — мирроры spec.md "Role-gated staff action buttons".
  const isFinalized = order.status === 'completed' || order.status === 'cancelled';
  const canAccept =
    order.status === 'paid' && (role === 'admin' || role === 'barista');
  const canReady =
    order.status === 'preparing' && (role === 'admin' || role === 'barista');
  const canHandout =
    order.status === 'ready' &&
    order.type === 'pickup' &&
    (role === 'admin' || role === 'barista');
  const canCancel = role === 'admin' && !isFinalized;
  const canRetryRefund = role === 'admin' && order.can_retry_refund;

  const any = canAccept || canReady || canHandout || canCancel || canRetryRefund;
  if (!any) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {canAccept && (
        <Button
          onClick={() => onTransition('preparing')}
          disabled={inFlight}
          data-testid="order-action-accept"
        >
          {t('pages.orders.actions.accept')}
        </Button>
      )}
      {canReady && (
        <Button
          onClick={() => onTransition('ready')}
          disabled={inFlight}
          data-testid="order-action-ready"
        >
          {t('pages.orders.actions.ready')}
        </Button>
      )}
      {canHandout && (
        <Button
          onClick={() => onTransition('completed')}
          disabled={inFlight}
          data-testid="order-action-handout"
        >
          {t('pages.orders.actions.handout')}
        </Button>
      )}
      {canCancel && (
        <Button
          variant="destructive"
          onClick={onCancelClick}
          disabled={inFlight}
          data-testid="order-action-cancel"
        >
          {t('pages.orders.actions.cancel')}
        </Button>
      )}
      {canRetryRefund && (
        <Button
          variant="outline"
          onClick={onRefundRetry}
          disabled={inFlight}
          data-testid="order-action-retry-refund"
        >
          <RefreshCw aria-hidden="true" />
          <span>{t('pages.orders.actions.retry_refund')}</span>
        </Button>
      )}
    </div>
  );
}

// START_CONTRACT: OrderDetailDialog
//   PURPOSE: Render the order detail modal with role-gated action buttons that
//            drive the order/payment state machines, and an admin-only cancel
//            confirmation. Reports successful commands via onAction so the
//            parent re-fetches; routes 409/other errors to onError for unified
//            handling.
//   INPUTS:  Props { order, open, onClose, onAction, onError? }
//   OUTPUTS: JSX.Element | null (null when no order selected).
//   SIDE_EFFECTS: PATCH updateOrderStatus / POST cancelAdminOrder /
//            POST retryRefund; transitions are server-validated (INV-016).
//            Reads useCurrentRole solely to decide which buttons to render.
//   LINKS:   INV-002 (server is the security boundary; this component only
//            controls UX visibility of buttons),
//            INV-013 (renders contact phone only from staff detail projection),
//            INV-014 (rendered item names come from snapshot fields),
//            INV-016 (each button is a state-machine transition trigger).
// END_CONTRACT: OrderDetailDialog
export function OrderDetailDialog({
  order,
  open,
  onClose,
  onAction,
  onError,
}: OrderDetailDialogProps) {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [inFlight, setInFlight] = useState(false);

  // Ранний return: модалка управляется извне, но без order рендерить нечего.
  if (!order) return null;

  const discountDisplay =
    order.discount_amount > 0
      ? `-${formatKopecks(order.discount_amount)}`
      : formatKopecks(order.discount_amount);

  async function runTransition(next: OrderStatus) {
    if (!order) return;
    setInFlight(true);
    try {
      await updateOrderStatus(order.id, next);
      onAction();
    } catch (err) {
      onError?.(err);
    } finally {
      setInFlight(false);
    }
  }

  async function runCancel() {
    if (!order) return;
    setInFlight(true);
    try {
      await cancelAdminOrder(order.id);
      setConfirmOpen(false);
      onAction();
    } catch (err) {
      // 409 (illegal transition) обрабатывается контейнером через onError.
      if (err instanceof ApiError && err.status === 409) {
        setConfirmOpen(false);
      }
      onError?.(err);
    } finally {
      setInFlight(false);
    }
  }

  async function runRefundRetry() {
    if (!order) return;
    setInFlight(true);
    try {
      await retryRefund(order.id);
      onAction();
    } catch (err) {
      onError?.(err);
    } finally {
      setInFlight(false);
    }
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) onClose();
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <span className="font-mono text-base">{shortId(order.id)}</span>
              <StatusBadge status={order.status} />
            </DialogTitle>
            <DialogDescription>
              {new Date(order.created_at).toLocaleString('ru-RU')}
            </DialogDescription>
          </DialogHeader>

          <section>
            <h3 className="text-sm font-medium mb-2">
              {t('pages.orders.detail.items')}
            </h3>
            {order.items.length === 0 ? (
              <p className="text-muted-foreground text-sm">—</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {order.items.map((item) => (
                  <li key={item.id} className="flex justify-between gap-2">
                    <span className="flex-1">
                      {item.menu_item_name_ru}
                      {item.size_label ? ` · ${item.size_label}` : ''}
                      {' × '}
                      {item.quantity}
                    </span>
                    <span className="font-mono">{formatKopecks(item.line_total)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="border-t pt-3 space-y-1 text-sm">
            <div className="flex justify-between">
              <span>{t('pages.orders.detail.subtotal')}</span>
              <span className="font-mono">{formatKopecks(order.subtotal)}</span>
            </div>
            <div className="flex justify-between">
              <span>{t('pages.orders.detail.discount')}</span>
              <span className="font-mono">{discountDisplay}</span>
            </div>
            <div className="flex justify-between">
              <span>{t('pages.orders.detail.delivery_fee')}</span>
              <span className="font-mono">{formatKopecks(order.delivery_fee)}</span>
            </div>
            <div className="flex justify-between font-medium border-t pt-1">
              <span>{t('pages.orders.detail.total')}</span>
              <span className="font-mono">{formatKopecks(order.total)}</span>
            </div>
          </section>

          <section className="rounded-md border p-3 text-sm space-y-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                {t('pages.orders.detail.customer')}
              </span>
              <span className="text-right">
                {order.customer_display_name ?? t('pages.orders.detail.customer_unknown')}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                {t('pages.orders.detail.contact_phone')}
              </span>
              {order.customer_contact_phone ? (
                <Button asChild variant="outline" size="sm">
                  <a
                    href={`tel:${order.customer_contact_phone}`}
                    data-testid="order-contact-phone"
                  >
                    <Phone aria-hidden="true" />
                    <span>{order.customer_contact_phone}</span>
                  </a>
                </Button>
              ) : (
                <span
                  className="text-muted-foreground"
                  data-testid="order-contact-phone-empty"
                >
                  {t('pages.orders.detail.contact_unavailable')}
                </span>
              )}
            </div>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="text-muted-foreground">
                {t('pages.orders.detail.user_id')}
              </span>
              <span className="font-mono">{shortId(order.user_id)}</span>
            </div>
          </section>

          {order.payment_status && (
            <section className="rounded-md border p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">
                  {t('pages.orders.detail.payment_status')}
                </span>
                <span
                  className="font-medium"
                  data-testid="order-payment-status"
                >
                  {t(`pages.orders.payment_status.${order.payment_status}`)}
                </span>
              </div>
            </section>
          )}

          <StaffActions
            order={order}
            onTransition={runTransition}
            onCancelClick={() => setConfirmOpen(true)}
            onRefundRetry={runRefundRetry}
            inFlight={inFlight}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={confirmOpen}
        onOpenChange={(next) => {
          if (!inFlight && !next) setConfirmOpen(false);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t('pages.orders.cancel_confirm.title')}</DialogTitle>
            <DialogDescription>
              {t('pages.orders.cancel_confirm.body')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={inFlight}
              data-testid="order-cancel-abort"
            >
              {t('pages.orders.cancel_confirm.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={runCancel}
              disabled={inFlight}
              data-testid="order-cancel-confirm"
            >
              {t('pages.orders.cancel_confirm.confirm')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
