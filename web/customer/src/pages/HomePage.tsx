import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="p-4 flex flex-col items-center gap-6 pt-16">
      <h1 className="text-2xl font-bold">{t('pages.home.title')}</h1>
      <p className="text-muted-foreground text-center">{t('pages.home.description')}</p>
      <Button asChild>
        <Link to="/menu">{t('nav.menu')}</Link>
      </Button>
    </div>
  );
}
