import { useTranslation } from 'react-i18next';

export function ProfilePage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.profile.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.profile.description')}</p>
    </div>
  );
}
