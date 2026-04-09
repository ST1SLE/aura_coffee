import { useTranslation } from 'react-i18next';

export function DashboardPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.dashboard.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.dashboard.description')}</p>
    </div>
  );
}
