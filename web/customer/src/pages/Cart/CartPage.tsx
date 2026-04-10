import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCartStore } from '@/store/cart';
import { Button } from '@/components/ui/button';
import { formatPrice } from '@/lib/formatPrice';
import { CartLine } from './CartLine';

export function CartPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const locale = lang === 'ru' ? 'ru' : 'en';

  const { status, items, subtotal, currency, refresh, updateQuantity, removeItem } =
    useCartStore();

  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => { refresh(); }, []);

  async function handleUpdate(itemId: string, qty: number) {
    setBusyId(itemId);
    try {
      await updateQuantity(itemId, qty);
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 410) {
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
      const status = (err as { status?: number })?.status;
      if (status === 410) {
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

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="p-4 space-y-3" data-testid="cart-loading">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="p-4 flex flex-col items-center gap-4">
        <p className="text-destructive">{t('cart.error')}</p>
        <Button variant="outline" onClick={refresh}>{t('cart.retry')}</Button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="p-4 flex flex-col items-center gap-4 text-center">
        <p className="text-muted-foreground">{t('cart.empty')}</p>
        <Button asChild>
          <Link to="/menu">{t('cart.emptyCta')}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 pb-24">
      {expiredToast && (
        <p role="status" className="mb-3 text-sm text-amber-600">
          {t('cart.expired')}
        </p>
      )}

      {items.map((item, idx) => {
        const id = `${item.menu_item_id}-${idx}`;
        return (
          <CartLine
            key={id}
            itemId={id}
            item={{ ...item, quantity: busyId === id ? item.quantity : item.quantity }}
            lang={lang}
            onUpdateQuantity={handleUpdate}
            onRemove={handleRemove}
          />
        );
      })}

      {/* Закреплённая строка итого */}
      <div className="fixed bottom-0 left-0 right-0 bg-background border-t px-4 py-3 flex justify-between items-center">
        <span className="font-medium">{t('cart.subtotal')}</span>
        <span className="font-bold text-lg">
          {formatPrice(subtotal, locale)} {currency}
        </span>
      </div>
    </div>
  );
}
