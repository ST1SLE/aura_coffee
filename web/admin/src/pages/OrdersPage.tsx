import { useTranslation } from 'react-i18next';

export function OrdersPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.orders.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.orders.description')}</p>
    </div>
  );
}
