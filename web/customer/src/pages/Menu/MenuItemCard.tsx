import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import type { PublicMenuItem } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';
import { MenuMedia } from './MenuMedia';

// START_MODULE_CONTRACT
//   PURPOSE: Menu grid card — media, name, base price, finite-stock hint, and
//            unavailable/sold-out badge. Pure presentation: dispatches one
//            onOpen callback when the user clicks/keyboard-activates an
//            available stocked item.
//   SCOPE:   MenuItemCard component.
//   DEPENDS: react-i18next, @/api/menuTypes (PublicMenuItem), @/lib/formatPrice,
//            ./MenuMedia.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu / §5.2 media.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuItemCard  - tile in the menu grid (pure presentation)
// END_MODULE_MAP

interface Props {
  item: PublicMenuItem;
  lang: 'ru' | 'en';
  onOpen: () => void;
}

export function MenuItemCard({ item, lang, onOpen }: Props) {
  const { t } = useTranslation();
  const soldOut = item.inventory_quantity === 0;
  const unavailable = !item.available || soldOut;

  return (
    <div
      role="button"
      tabIndex={unavailable ? -1 : 0}
      aria-disabled={unavailable}
      onClick={unavailable ? undefined : onOpen}
      onKeyDown={(e) => {
        if (!unavailable && (e.key === 'Enter' || e.key === ' ')) onOpen();
      }}
      className={[
        'group relative flex min-h-[17rem] cursor-pointer select-none flex-col overflow-hidden rounded-lg border border-border/75 bg-card shadow-[0_16px_34px_rgba(58,46,37,0.10)] transition duration-200',
        unavailable
          ? 'opacity-60 cursor-not-allowed pointer-events-none'
          : 'hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-[0_18px_38px_rgba(58,46,37,0.14)]',
      ].join(' ')}
    >
      <MenuMedia
        item={item}
        alt={item.name}
        className="h-48 w-full bg-secondary sm:h-44"
        controls={false}
      />
      <div className="flex flex-1 flex-col gap-3 p-3">
        <span className="font-display min-h-10 text-base font-semibold leading-tight text-foreground">
          {item.name}
        </span>
        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="aura-numeric rounded-full bg-secondary px-3 py-1 text-sm font-semibold text-primary">
            {formatPrice(item.base_price, lang === 'ru' ? 'ru' : 'en')}
          </span>
          {!unavailable && (
            <span
              aria-hidden="true"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform group-hover:scale-105"
            >
              <Plus className="h-4 w-4" />
            </span>
          )}
        </div>
      </div>
      {item.inventory_quantity != null && item.inventory_quantity > 0 && (
        <span className="font-display absolute left-2 top-2 rounded-full border border-border/70 bg-card/90 px-2.5 py-1 text-xs font-semibold text-foreground shadow-[0_8px_18px_rgba(58,46,37,0.10)] backdrop-blur">
          {t('menu.stockLeft', { count: item.inventory_quantity })}
        </span>
      )}
      {unavailable && (
        <span className="font-display absolute right-2 top-2 rounded-full bg-destructive px-2.5 py-1 text-xs font-semibold text-destructive-foreground shadow-[0_8px_18px_rgba(163,79,53,0.18)]">
          {soldOut ? t('menu.soldOut') : t('menu.unavailable')}
        </span>
      )}
    </div>
  );
}
