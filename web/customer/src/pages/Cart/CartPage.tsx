import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ShoppingBag } from 'lucide-react';
import { useCartStore } from '@/store/cart';
import { ApiError } from '@/api/client';
import type { RepeatOrderSkippedEntry } from '@/api/orders';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';
import { CartLine } from './CartLine';

// START_MODULE_CONTRACT
//   PURPOSE: Cart route page — drives the zustand cart store (refresh on mount),
//            renders skeleton/error/empty/list states, and handles 410 EXPIRED
//            specifically by showing a transient toast and refetching. Repeat-
//            order skipped entries are shown from navigation state.
//            This is the "real" CartPage; pages/CartPage.tsx is a placeholder
//            stub from earlier scaffolding.
//   SCOPE:   CartPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/store/cart (useCartStore),
//            @/api/client (ApiError), @/api/orders (RepeatOrderSkippedEntry type),
//            @/lib/formatPrice, @/components/ui/button, ./CartLine.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart, §7.7;
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
//                 Reads repeat-order skipped entries from router state.
//                 INV-014 — subtotal/lines from server snapshots.
//   LINKS:   PDD §5 cart, §7.7 repeat order; ApiError(410) -> refetch + toast.
// END_CONTRACT: CartPage
export function CartPage() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru' : 'en';
  const repeatSkipped =
    (
      location.state as {
        repeatOrderSkipped?: RepeatOrderSkippedEntry[];
      } | null
    )?.repeatOrderSkipped ?? [];

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

  function repeatSkippedMessage(entry: RepeatOrderSkippedEntry): string {
    if (lang === 'ru') {
      return (
        entry.message_ru ?? entry.message_en ?? t('cart.repeatSkippedFallback')
      );
    }
    return (
      entry.message_en ?? entry.message_ru ?? t('cart.repeatSkippedFallback')
    );
  }

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="space-y-4 px-4 py-5 md:px-6" data-testid="cart-loading">
        <div className="h-20 animate-pulse rounded-lg bg-muted/70" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 animate-pulse rounded-lg bg-muted" />
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
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
        <div className="aura-surface flex w-full max-w-sm flex-col items-center gap-4 rounded-lg p-6">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-primary">
            <ShoppingBag className="h-6 w-6" aria-hidden="true" />
          </div>
          <p className="text-muted-foreground">{t('cart.empty')}</p>
          <Button asChild>
            <Link to="/menu">{t('cart.emptyCta')}</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-5 pb-44 md:px-6 md:pb-32">
      <div className="aura-surface flex items-center justify-between gap-3 rounded-lg p-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-normal">
            {t('cart.title')}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('pages.cart.description')}
          </p>
        </div>
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

      {repeatSkipped.length > 0 && (
        <div
          role="status"
          className="rounded-md border border-primary/40 bg-primary/10 px-3 py-2 text-sm text-primary"
        >
          <p className="font-medium">{t('cart.repeatSkippedTitle')}</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {repeatSkipped.map((entry, index) => (
              <li key={`${entry.reason}-${index}`}>
                {repeatSkippedMessage(entry)}
              </li>
            ))}
          </ul>
        </div>
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

      <div
        className="fixed bottom-20 left-0 right-0 z-30 px-4 py-3 md:bottom-3"
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
      >
        <div className="aura-surface mx-auto grid w-full max-w-5xl gap-3 rounded-lg bg-background/95 p-3 backdrop-blur md:flex md:items-center md:justify-between">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">{t('cart.subtotal')}</span>
            <span className="text-xl font-bold text-primary">
              {formatPrice(subtotal, locale)} {currency}
            </span>
          </div>
          <Button asChild className="w-full md:w-auto">
            <Link to="/checkout">{t('nav.checkout')}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
