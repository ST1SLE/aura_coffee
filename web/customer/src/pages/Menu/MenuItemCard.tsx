import { useTranslation } from 'react-i18next';
import type { PublicMenuItem } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';

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
        'rounded-lg border p-3 flex flex-col gap-2 cursor-pointer select-none',
        unavailable
          ? 'opacity-50 cursor-not-allowed pointer-events-none'
          : 'hover:bg-accent',
      ].join(' ')}
    >
      {item.image_url && (
        <img
          src={item.image_url}
          alt={item.name}
          className="w-full h-24 object-cover rounded-md"
        />
      )}
      <span className="text-sm font-medium leading-tight">{item.name}</span>
      <span className="text-xs text-muted-foreground">
        {formatPrice(item.base_price, lang === 'ru' ? 'ru' : 'en')}
      </span>
      {unavailable && (
        <span className="text-xs text-destructive font-medium">
          {t('menu.unavailable')}
        </span>
      )}
    </div>
  );
}
