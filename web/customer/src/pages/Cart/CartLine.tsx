import { useTranslation } from 'react-i18next';
import type { CartItemResponse } from '@/api/cartTypes';
import { formatPrice } from '@/lib/formatPrice';
import { Button } from '@/components/ui/button';

interface Props {
  item: CartItemResponse;
  lang: 'ru' | 'en';
  onUpdateQuantity: (itemId: string, quantity: number) => void;
  onRemove: (itemId: string) => void;
  /** Уникальный идентификатор строки (индекс или id) */
  itemId: string;
}

export function CartLine({ item, lang, onUpdateQuantity, onRemove, itemId }: Props) {
  const { t } = useTranslation();
  const locale = lang === 'ru' ? 'ru' : 'en';
  const name = lang === 'ru' ? item.menu_item_snapshot.name_ru : item.menu_item_snapshot.name_en;

  const modifierNames = item.modifiers_snapshot
    .map((m) => (lang === 'ru' ? m.name_ru : m.name_en))
    .join(t('cart.modifierSeparator'));

  return (
    <div className="flex flex-col gap-1 py-3 border-b last:border-b-0">
      <div className="flex justify-between items-start">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-sm">{name}</span>
          {item.size_snapshot && (
            <span className="text-xs text-muted-foreground">{item.size_snapshot.label}</span>
          )}
          {modifierNames && (
            <span className="text-xs text-muted-foreground">{modifierNames}</span>
          )}
        </div>
        <button
          aria-label={t('cart.remove')}
          onClick={() => onRemove(itemId)}
          className="text-muted-foreground hover:text-destructive text-sm ml-4"
        >
          ✕
        </button>
      </div>
      <div className="flex items-center justify-between mt-1">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label={t('cart.decrement')}
            onClick={() =>
              item.quantity <= 1
                ? onRemove(itemId)
                : onUpdateQuantity(itemId, item.quantity - 1)
            }
          >
            −
          </Button>
          <span className="w-6 text-center text-sm">{item.quantity}</span>
          <Button
            variant="outline"
            size="icon"
            aria-label={t('cart.increment')}
            disabled={item.quantity >= 99}
            onClick={() => onUpdateQuantity(itemId, item.quantity + 1)}
          >
            +
          </Button>
        </div>
        <div className="flex flex-col items-end text-sm">
          <span className="text-muted-foreground">{formatPrice(item.unit_price, locale)} × {item.quantity}</span>
          <span className="font-semibold">{formatPrice(item.line_total, locale)}</span>
        </div>
      </div>
    </div>
  );
}
