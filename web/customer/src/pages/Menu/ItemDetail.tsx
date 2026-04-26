import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PublicMenuItem, PublicMenuSizeOption, PublicMenuModifier } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';
import { Button } from '@/components/ui/button';
import { useCartStore } from '@/store/cart';

// START_MODULE_CONTRACT
//   PURPOSE: Bottom-sheet modal that lets the user pick a size + modifiers for
//            a menu item, shows the running price (display-only — server
//            recomputes on add), and adds the configured item to the cart.
//   SCOPE:   ItemDetail component.
//   DEPENDS: react, react-i18next, @/api/menuTypes, @/lib/formatPrice,
//            @/components/ui/button, @/store/cart.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu / §5 cart.
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
//   PURPOSE: Render the size/modifier picker and call useCartStore.addItem on
//            confirm.
//   INPUTS:  Props — item: PublicMenuItem, lang: 'ru'|'en', onClose: () => void.
//   OUTPUTS: JSX — modal dialog (role="dialog" aria-modal).
//   SIDE_EFFECTS: cart store addItem (HTTP POST /cart/items); shows
//                 success/error toast and auto-closes after success.
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
  const [selectedModifiers, setSelectedModifiers] = useState<PublicMenuModifier[]>([]);
  const [busy, setBusy] = useState(false);
  const [toastMsg, setToastMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const locale = lang === 'ru' ? 'ru' : 'en';

  const currentPrice =
    (selectedSize?.price ?? item.base_price) +
    selectedModifiers.reduce((s, m) => s + m.price, 0);

  const canAdd = item.size_options.length === 0 || selectedSize !== null;

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
        quantity: 1,
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
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-t-2xl bg-background p-5 space-y-4">
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-semibold">{item.name}</h2>
          <button
            aria-label="close"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground ml-4"
          >
            ✕
          </button>
        </div>

        {item.description && (
          <p className="text-sm text-muted-foreground">{item.description}</p>
        )}

        {item.size_options.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">{t('menu.selectSize')}</p>
            <div className="flex gap-2 flex-wrap">
              {item.size_options.map((sz) => (
                <button
                  key={sz.id}
                  disabled={!sz.available}
                  aria-pressed={selectedSize?.id === sz.id}
                  onClick={() => sz.available && setSelectedSize(sz)}
                  className={[
                    'rounded-full px-3 py-1 text-sm border',
                    !sz.available && 'opacity-40 cursor-not-allowed',
                    selectedSize?.id === sz.id
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-input hover:bg-accent',
                  ].join(' ')}
                >
                  {sz.label} — {formatPrice(sz.price, locale)}
                </button>
              ))}
            </div>
          </div>
        )}

        {item.modifiers.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">{t('menu.modifiers')}</p>
            <div className="flex gap-2 flex-wrap">
              {item.modifiers.map((mod) => {
                const active = selectedModifiers.some((m) => m.id === mod.id);
                return (
                  <button
                    key={mod.id}
                    disabled={!mod.available}
                    aria-pressed={active}
                    onClick={() => mod.available && toggleModifier(mod)}
                    className={[
                      'rounded-full px-3 py-1 text-sm border',
                      !mod.available && 'opacity-40 cursor-not-allowed',
                      active
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'border-input hover:bg-accent',
                    ].join(' ')}
                  >
                    {mod.name} +{formatPrice(mod.price, locale)}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <span className="font-semibold text-lg">{formatPrice(currentPrice, locale)}</span>
          <Button
            onClick={handleAddToCart}
            disabled={!canAdd || busy}
          >
            {t('menu.addToCart')}
          </Button>
        </div>

        {toastMsg && (
          <p
            role="status"
            className={toastMsg.type === 'success' ? 'text-sm text-green-600' : 'text-sm text-destructive'}
          >
            {toastMsg.text}
          </p>
        )}
      </div>
    </div>
  );
}
