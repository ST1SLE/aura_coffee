import { useTranslation } from 'react-i18next';
import type { MenuItemResponse } from '@/api/menuTypes';
import { formatPrice } from '@/lib/formatPrice';

interface Props {
  item: MenuItemResponse;
  lang: 'ru' | 'en';
  onOpen: () => void;
}

export function MenuItemCard({ item, lang, onOpen }: Props) {
  const { t } = useTranslation();
  const unavailable = !item.available || item.archived;
  const name = lang === 'ru' ? item.name_ru : item.name_en;

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
          alt={name}
          className="w-full h-24 object-cover rounded-md"
        />
      )}
      <span className="text-sm font-medium leading-tight">{name}</span>
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
