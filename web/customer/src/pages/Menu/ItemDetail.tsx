import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Minus, Plus, ShoppingBag, X } from 'lucide-react';
import type {
  PublicMenuItem,
  PublicMenuSizeOption,
  PublicMenuModifier,
} from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';
import { Button } from '@/components/ui/button';
import { useCartStore } from '@/store/cart';
import { MenuMedia } from './MenuMedia';

// START_MODULE_CONTRACT
//   PURPOSE: Bottom-sheet modal that lets the user pick a size + modifiers for
//            a menu item, shows finite-stock quantity controls and the running
//            price (display-only — server recomputes on add), and adds the
//            configured item to the cart.
//   SCOPE:   ItemDetail component.
//   DEPENDS: react, react-i18next, @/api/menuTypes, @/lib/formatPrice,
//            @/components/ui/button, @/store/cart, ./MenuMedia.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu / §5 cart,
//            PDD §5.2 menu media.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ItemDetail  - bottom-sheet modal for size + modifier selection + add-to-cart
// END_MODULE_MAP

interface Props {
  item: PublicMenuItem;
  lang: 'ru' | 'en';
  onClose: () => void;
}

// START_CONTRACT: ItemDetail
//   PURPOSE: Render the size/modifier/quantity picker and call
//            useCartStore.addItem on confirm.
//   INPUTS:  Props — item: PublicMenuItem, lang: 'ru'|'en', onClose: () => void.
//   OUTPUTS: JSX — modal dialog (role="dialog" aria-modal).
//   SIDE_EFFECTS: cart store addItem (HTTP POST /cart/items); shows
//                 success/error toast and auto-closes after success. Quantity
//                 is capped by server-provided inventory_quantity for UX only;
//                 Core API enforces the cap.
//                 NOTE: currentPrice in the UI is display-only — the server
//                 re-prices on the back end (AGENTS.md "Prices always from server").
//   LINKS:   PDD §3 / §5; consumed by MenuPage.
// END_CONTRACT: ItemDetail
export function ItemDetail({ item, lang, onClose }: Props) {
  const { t } = useTranslation();
  const addToCart = useCartStore((s) => s.addItem);

  const availableSizes = item.size_options.filter((s) => s.available);
  const [selectedSize, setSelectedSize] = useState<PublicMenuSizeOption | null>(
    availableSizes[0] ?? null,
  );
  const [selectedModifiers, setSelectedModifiers] = useState<
    PublicMenuModifier[]
  >([]);
  const inventoryCap = item.inventory_quantity ?? 99;
  const maxQuantity = Math.max(0, Math.min(99, inventoryCap));
  const [quantity, setQuantity] = useState(maxQuantity > 0 ? 1 : 0);
  const [busy, setBusy] = useState(false);
  const [toastMsg, setToastMsg] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const locale = lang === 'ru' ? 'ru' : 'en';

  const currentPrice =
    (selectedSize?.price ?? item.base_price) +
    selectedModifiers.reduce((s, m) => s + m.price, 0);

  const hasRequiredSize = item.size_options.length === 0 || selectedSize !== null;
  const canAdd = hasRequiredSize && item.available && quantity > 0;

  function toggleModifier(mod: PublicMenuModifier) {
    setSelectedModifiers((prev) =>
      prev.some((m) => m.id === mod.id)
        ? prev.filter((m) => m.id !== mod.id)
        : [...prev, mod],
    );
  }

  async function handleAddToCart() {
    setBusy(true);
    try {
      await addToCart({
        menu_item_id: item.id,
        size_option_id: selectedSize?.id ?? null,
        modifier_ids: selectedModifiers.map((m) => m.id),
        quantity,
      });
      setToastMsg({ type: 'success', text: t('menu.added') });
      setTimeout(onClose, 800);
    } catch {
      setToastMsg({ type: 'error', text: t('menu.error') });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/35 backdrop-blur-md md:items-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[94vh] w-full max-w-xl flex-col overflow-hidden rounded-t-lg border border-border/80 bg-card shadow-[0_24px_70px_rgba(58,46,37,0.22)] md:rounded-lg">
        <div className="relative">
          <MenuMedia
            item={item}
            alt={item.name}
            className="h-[22rem] w-full bg-secondary md:h-96"
          />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-card to-transparent" />
          <button
            aria-label="close"
            onClick={onClose}
            className="absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-full border border-border/80 bg-card/90 text-foreground shadow-[0_8px_18px_rgba(58,46,37,0.12)] backdrop-blur transition-colors hover:bg-secondary"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="space-y-6 pb-24">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-normal">
                {item.name}
              </h2>
              {item.description && (
                <p className="text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
              )}
            </div>

            {item.size_options.length > 0 && (
              <div className="aura-surface-soft rounded-lg p-3">
                <p className="font-display mb-2 text-sm font-semibold">
                  {t('menu.selectSize')}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {item.size_options.map((sz) => (
                    <button
                      key={sz.id}
                      disabled={!sz.available}
                      aria-pressed={selectedSize?.id === sz.id}
                      onClick={() => sz.available && setSelectedSize(sz)}
                      className={[
                        'font-display min-h-12 rounded-md border px-3 text-left text-sm font-semibold transition-colors',
                        !sz.available && 'opacity-40 cursor-not-allowed',
                        selectedSize?.id === sz.id
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border/70 bg-card text-foreground hover:bg-secondary',
                      ].join(' ')}
                    >
                      {sz.label} — {formatPrice(sz.price, locale)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {item.modifiers.length > 0 && (
              <div className="aura-surface-soft rounded-lg p-3">
                <p className="font-display mb-2 text-sm font-semibold">
                  {t('menu.modifiers')}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {item.modifiers.map((mod) => {
                    const active = selectedModifiers.some(
                      (m) => m.id === mod.id,
                    );
                    return (
                      <button
                        key={mod.id}
                        disabled={!mod.available}
                        aria-pressed={active}
                        onClick={() => mod.available && toggleModifier(mod)}
                        className={[
                          'font-display min-h-12 rounded-md border px-3 text-left text-sm font-semibold transition-colors',
                          !mod.available && 'opacity-40 cursor-not-allowed',
                          active
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border/70 bg-card text-foreground hover:bg-secondary',
                        ].join(' ')}
                      >
                        {mod.name} +{formatPrice(mod.price, locale)}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="aura-surface-soft flex items-center justify-between gap-3 rounded-lg p-3">
              <div className="min-w-0">
                <p className="font-display text-sm font-semibold">
                  {t('menu.quantity')}
                </p>
                {item.inventory_quantity != null && (
                  <p className="text-xs text-muted-foreground">
                    {item.inventory_quantity > 0
                      ? t('menu.stockLeft', { count: item.inventory_quantity })
                      : t('menu.soldOut')}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1 rounded-full bg-secondary/70 p-1">
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={t('cart.decrement')}
                  disabled={quantity <= 1}
                  className="h-8 w-8 rounded-full border-border/70 bg-card"
                  onClick={() => setQuantity((current) => Math.max(1, current - 1))}
                >
                  <Minus className="h-4 w-4" aria-hidden="true" />
                </Button>
                <span className="w-8 text-center text-sm font-semibold">
                  {quantity}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={t('cart.increment')}
                  disabled={quantity >= maxQuantity}
                  className="h-8 w-8 rounded-full border-border/70 bg-card"
                  onClick={() =>
                    setQuantity((current) => Math.min(maxQuantity, current + 1))
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </div>

            {toastMsg && (
              <p
                role="status"
                className={
                  toastMsg.type === 'success'
                    ? 'text-sm text-success'
                    : 'text-sm text-destructive'
                }
              >
                {toastMsg.text}
              </p>
            )}
          </div>
        </div>

        <div
          className="border-t border-border/80 bg-card/95 px-5 py-3 shadow-[0_-14px_32px_rgba(58,46,37,0.10)] backdrop-blur"
          style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
        >
          <div className="grid gap-3 sm:flex sm:items-center sm:justify-between">
            <span className="aura-numeric min-w-0 text-2xl font-semibold text-primary">
              {formatPrice(currentPrice, locale)}
            </span>
            <Button
              onClick={handleAddToCart}
              disabled={!canAdd || busy}
              className="w-full shrink-0 px-4 sm:w-auto"
              style={{ flexShrink: 0 }}
            >
              <ShoppingBag className="h-4 w-4" aria-hidden="true" />
              {t('menu.addToCart')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
