import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import type { PublicMenuItem } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';
import { MenuMedia } from './MenuMedia';

// START_MODULE_CONTRACT
//   PURPOSE: Menu grid card — media, name, base price, finite-stock hint, and
//            unavailable/sold-out badge. Pure presentation: dispatches one
//            onOpen callback when the user activates an available stocked item.
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
  onOpen: (trigger: HTMLButtonElement) => void;
}

// START_CONTRACT: MenuItemCard
//   PURPOSE: Render a media-first menu card that opens an available item detail
//            view while keeping price/name overlays readable on image/video.
//   INPUTS:  Props { item, lang, onOpen }.
//   OUTPUTS: JSX.Element — native button product tile.
//   SIDE_EFFECTS: Calls onOpen for available stocked items; no cart/order/API
//                 mutation and no logging.
//   LINKS:   PDD §5.2 menu media; INV-014 server-owned item snapshots.
// END_CONTRACT: MenuItemCard
export function MenuItemCard({ item, lang, onOpen }: Props) {
  const { t } = useTranslation();
  const soldOut = item.inventory_quantity === 0;
  const unavailable = !item.available || soldOut;

  return (
    <button
      type="button"
      disabled={unavailable}
      onClick={unavailable ? undefined : (e) => onOpen(e.currentTarget)}
      className={[
        'group relative flex min-h-[18rem] w-full cursor-pointer select-none flex-col overflow-hidden rounded-lg border border-border/75 bg-secondary text-left shadow-[0_16px_34px_rgba(30,24,19,0.22)] transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:min-h-[17rem]',
        unavailable
          ? 'opacity-60 cursor-not-allowed pointer-events-none'
          : 'hover:-translate-y-0.5 hover:border-primary/70 hover:shadow-[0_20px_42px_rgba(30,24,19,0.28)]',
      ].join(' ')}
    >
      <MenuMedia
        item={item}
        alt={item.name}
        className="absolute inset-0 h-full w-full bg-secondary"
        controls={false}
      />

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col gap-2 bg-gradient-to-t from-foreground/85 via-foreground/35 to-transparent p-3 pt-24 text-primary-foreground">
        <span className="font-display line-clamp-2 min-h-10 text-base font-semibold leading-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
          {item.name}
        </span>
        <div className="flex items-end justify-between gap-2">
          <span className="aura-numeric rounded-full border border-primary-foreground/20 bg-card/90 px-3 py-1 text-sm font-semibold text-foreground shadow-[0_10px_24px_rgba(0,0,0,0.20)] backdrop-blur-md">
            {formatPrice(item.base_price, lang === 'ru' ? 'ru' : 'en')}
          </span>
          {!unavailable && (
            <span
              aria-hidden="true"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_12px_26px_rgba(0,0,0,0.24)] transition-transform group-hover:scale-105"
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
    </button>
  );
}
