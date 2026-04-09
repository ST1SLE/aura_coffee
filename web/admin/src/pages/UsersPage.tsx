import { useTranslation } from 'react-i18next';

export function UsersPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.users.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.users.description')}</p>
    </div>
  );
}
