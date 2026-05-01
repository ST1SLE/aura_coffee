import { useTranslation } from 'react-i18next';
import { Minus, Plus, X } from 'lucide-react';
import type { CartItemResponse } from '@/api/cartTypes';
import { formatPrice } from '@/lib/formatPrice';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: One row in the cart list — renders the menu item name, optional
//            size + modifier list, qty stepper (with auto-remove at 0), and
//            line totals. Delegates persistence to its onUpdateQuantity /
//            onRemove props (CartPage owns the store + error handling).
//   SCOPE:   CartLine component.
//   DEPENDS: react-i18next, @/api/cartTypes (CartItemResponse), @/lib/formatPrice,
//            @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart;
//            INV-014 — name_ru/name_en come from server snapshots, never recomputed.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CartLine  - cart row with qty stepper and remove button
// END_MODULE_MAP

interface Props {
  item: CartItemResponse;
  lang: 'ru' | 'en';
  onUpdateQuantity: (itemId: string, quantity: number) => void;
  onRemove: (itemId: string) => void;
  /** Уникальный идентификатор строки (индекс или id) */
  itemId: string;
}

// START_CONTRACT: CartLine
//   PURPOSE: Render one cart line and surface user actions through callbacks.
//   INPUTS:  Props — item: CartItemResponse, lang: 'ru'|'en',
//            onUpdateQuantity: (itemId, qty) => void, onRemove: (itemId) => void,
//            itemId: string.
//   OUTPUTS: JSX — full row (name + variants + stepper + price).
//   SIDE_EFFECTS: only via the callbacks. Auto-remove when decrementing from 1.
//                 INV-014 — prices/snapshot fields rendered as-is (no client math).
//   LINKS:   PDD §5; consumed by Cart/CartPage.
// END_CONTRACT: CartLine
export function CartLine({
  item,
  lang,
  onUpdateQuantity,
  onRemove,
  itemId,
}: Props) {
  const { t } = useTranslation();
  const locale = lang === 'ru' ? 'ru' : 'en';
  const name =
    lang === 'ru'
      ? item.menu_item_snapshot.name_ru
      : item.menu_item_snapshot.name_en;

  const modifierNames = item.modifiers_snapshot
    .map((m) => (lang === 'ru' ? m.name_ru : m.name_en))
    .join(t('cart.modifierSeparator'));

  return (
    <div className="aura-surface flex flex-col gap-4 rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-base font-semibold leading-tight">{name}</span>
          {item.size_snapshot && (
            <span className="text-xs text-muted-foreground">
              {item.size_snapshot.label}
            </span>
          )}
          {modifierNames && (
            <span className="text-xs text-muted-foreground">
              {modifierNames}
            </span>
          )}
        </div>
        <button
          aria-label={t('cart.remove')}
          onClick={() => onRemove(itemId)}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary/70 text-muted-foreground transition-colors hover:bg-secondary hover:text-destructive"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-full bg-secondary/70 p-1">
          <Button
            variant="outline"
            size="icon"
            aria-label={t('cart.decrement')}
            className="h-8 w-8 rounded-full border-white/10 bg-background/70"
            onClick={() =>
              item.quantity <= 1
                ? onRemove(itemId)
                : onUpdateQuantity(itemId, item.quantity - 1)
            }
          >
            <Minus className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="w-8 text-center text-sm font-semibold">
            {item.quantity}
          </span>
          <Button
            variant="outline"
            size="icon"
            aria-label={t('cart.increment')}
            disabled={item.quantity >= 99}
            className="h-8 w-8 rounded-full border-white/10 bg-background/70"
            onClick={() => onUpdateQuantity(itemId, item.quantity + 1)}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <div className="flex flex-col items-end text-sm">
          <span className="text-muted-foreground">
            {formatPrice(item.unit_price, locale)} × {item.quantity}
          </span>
          <span className="font-semibold text-primary">
            {formatPrice(item.line_total, locale)}
          </span>
        </div>
      </div>
    </div>
  );
}
