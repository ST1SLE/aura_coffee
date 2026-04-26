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

  const { status, items, subtotal, currency, refresh, updateQuantity, removeItem, clearCart } =
    useCartStore();

  const [, setBusyId] = useState<string | null>(null);

  useEffect(() => { refresh(); }, []);

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
      <div className="p-4 space-y-3" data-testid="cart-loading">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="p-4 flex flex-col items-center gap-4">
        <p className="text-destructive">{t('cart.error')}</p>
        <Button variant="outline" onClick={refresh}>{t('cart.retry')}</Button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="p-4 flex flex-col items-center gap-4 text-center">
        <p className="text-muted-foreground">{t('cart.empty')}</p>
        <Button asChild>
          <Link to="/menu">{t('cart.emptyCta')}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 pb-24">
      {expiredToast && (
        <p role="status" className="mb-3 text-sm text-amber-600">
          {t('cart.expired')}
        </p>
      )}

      <div className="flex justify-end mb-3">
        <Button variant="outline" size="sm" onClick={clearCart}>
          {t('cart.clearCart')}
        </Button>
      </div>

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

      {/* Закреплённая строка итого */}
      <div className="fixed bottom-0 left-0 right-0 bg-background border-t px-4 py-3 flex justify-between items-center">
        <span className="font-medium">{t('cart.subtotal')}</span>
        <span className="font-bold text-lg">
          {formatPrice(subtotal, locale)} {currency}
        </span>
      </div>
    </div>
  );
}
