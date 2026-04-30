import { useTranslation } from 'react-i18next';
import type { PublicMenuItem } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';
import { MenuMedia } from './MenuMedia';

// START_MODULE_CONTRACT
//   PURPOSE: Menu grid card — media, name, base price, "unavailable" badge.
//            Pure presentation: dispatches one onOpen callback when the user
//            clicks/keyboard-activates an available item.
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
  const unavailable = !item.available;

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
        'group relative min-h-[17rem] overflow-hidden rounded-lg border border-border bg-card cursor-pointer select-none shadow-sm transition-transform',
        unavailable
          ? 'opacity-50 cursor-not-allowed pointer-events-none'
          : 'hover:-translate-y-0.5 hover:border-primary/60',
      ].join(' ')}
    >
      <MenuMedia
        item={item}
        alt={item.name}
        className="h-48 w-full bg-secondary"
        controls={false}
      />
      <div className="flex flex-1 flex-col gap-2 p-3">
        <span className="text-base font-semibold leading-tight">
          {item.name}
        </span>
        <span className="mt-auto text-sm text-primary">
          {formatPrice(item.base_price, lang === 'ru' ? 'ru' : 'en')}
        </span>
      </div>
      {unavailable && (
        <span className="absolute right-2 top-2 rounded-md bg-destructive px-2 py-1 text-xs font-medium text-destructive-foreground">
          {t('menu.unavailable')}
        </span>
      )}
    </div>
  );
}
