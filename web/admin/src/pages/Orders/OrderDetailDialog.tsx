import { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  ApiError,
} from '@/api/admin-orders';
import type { OrderResponse, OrderStatus } from '@/api/admin-orders';

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
  order: OrderResponse | null;
  open: boolean;
  onClose: () => void;
  onAction: () => void;
  onError?: (error: unknown) => void;
}

interface StaffActionsProps {
  order: OrderResponse;
  onTransition: (next: OrderStatus) => Promise<void>;
  onCancelClick: () => void;
  inFlight: boolean;
}

function StaffActions({ order, onTransition, onCancelClick, inFlight }: StaffActionsProps) {
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

  const any = canAccept || canReady || canHandout || canCancel;
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
    </div>
  );
}

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

          <section className="text-xs text-muted-foreground">
            {t('pages.orders.detail.user_id')}: <span className="font-mono">{shortId(order.user_id)}</span>
          </section>

          <StaffActions
            order={order}
            onTransition={runTransition}
            onCancelClick={() => setConfirmOpen(true)}
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
