import { useTranslation } from 'react-i18next';

export function PromosPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.promos.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.promos.description')}</p>
    </div>
  );
}
