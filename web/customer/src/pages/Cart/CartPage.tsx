import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCartStore } from '@/store/cart';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';
import { CartLine } from './CartLine';

// START_MODULE_CONTRACT
//   PURPOSE: Cart route page — drives the zustand cart store (refresh on mount),
//            renders skeleton/error/empty/list states, and handles 410 EXPIRED
//            specifically by showing a transient toast and refetching.
//            This is the "real" CartPage; pages/CartPage.tsx is a placeholder
//            stub from earlier scaffolding.
//   SCOPE:   CartPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/store/cart (useCartStore),
//            @/api/client (ApiError), @/lib/formatPrice, @/components/ui/button,
//            ./CartLine.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart;
//            INV-014 (snapshot rendering — never recompute prices).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CartPage  - /cart route — list + qty stepper + sticky subtotal
// END_MODULE_MAP

// START_CONTRACT: CartPage
//   PURPOSE: Render the customer's cart with optimistic mutations through the
//            zustand store and graceful expired-cart handling.
//   INPUTS:  none (reads useCartStore + i18n).
//   OUTPUTS: JSX — skeleton / error / empty / list with sticky footer.
//   SIDE_EFFECTS: useCartStore.refresh on mount; updateQuantity / removeItem /
//                 clearCart through callbacks; transient expiredToast state.
//                 INV-014 — subtotal/lines from server snapshots.
//   LINKS:   PDD §5 cart; ApiError(410) -> refetch + toast.
// END_CONTRACT: CartPage
export function CartPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru' : 'en';

  const {
    status,
    items,
    subtotal,
    currency,
    refresh,
    updateQuantity,
    removeItem,
    clearCart,
  } = useCartStore();

  const [, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpdate(itemId: string, qty: number) {
    setBusyId(itemId);
    try {
      await updateQuantity(itemId, qty);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 410) {
        showExpiredToast();
        await refresh();
      }
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemove(itemId: string) {
    setBusyId(itemId);
    try {
      await removeItem(itemId);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 410) {
        showExpiredToast();
        await refresh();
      }
    } finally {
      setBusyId(null);
    }
  }

  const [expiredToast, setExpiredToast] = useState(false);
  function showExpiredToast() {
    setExpiredToast(true);
    setTimeout(() => setExpiredToast(false), 3000);
  }

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="space-y-4 px-4 py-5 md:px-6" data-testid="cart-loading">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-28 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-destructive">{t('cart.error')}</p>
        <Button variant="outline" onClick={refresh}>
          {t('cart.retry')}
        </Button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-muted-foreground">{t('cart.empty')}</p>
        <Button asChild>
          <Link to="/menu">{t('cart.emptyCta')}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-5 pb-36 md:px-6 md:pb-28">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-normal">
          {t('cart.title')}
        </h1>
        <Button variant="outline" size="sm" onClick={clearCart}>
          {t('cart.clearCart')}
        </Button>
      </div>

      {expiredToast && (
        <p
          role="status"
          className="rounded-md border border-primary/40 bg-primary/10 px-3 py-2 text-sm text-primary"
        >
          {t('cart.expired')}
        </p>
      )}

      <div className="space-y-3">
        {items.map((item) => (
          <CartLine
            key={item.line_id}
            itemId={item.line_id}
            item={item}
            lang={lang}
            onUpdateQuantity={handleUpdate}
            onRemove={handleRemove}
          />
        ))}
      </div>

      {/* Закреплённая строка итого */}
      <div
        className="fixed bottom-16 left-0 right-0 z-30 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:bottom-0"
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
      >
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between">
          <span className="font-medium">{t('cart.subtotal')}</span>
          <span className="text-lg font-bold text-primary">
            {formatPrice(subtotal, locale)} {currency}
          </span>
        </div>
      </div>
    </div>
  );
}
