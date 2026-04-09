import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();

  const toggle = () => {
    const next = i18n.language === 'ru' ? 'en' : 'ru';
    i18n.changeLanguage(next);
  };

  return (
    <Button variant="ghost" size="sm" onClick={toggle}>
      {i18n.language === 'ru' ? t('language.en') : t('language.ru')}
    </Button>
  );
}
