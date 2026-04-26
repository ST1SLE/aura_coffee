import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Header button that toggles between RU and EN by calling
//            i18n.changeLanguage; the persistence is handled by LanguageDetector
//            with localStorage cache (see i18n/config.ts).
//   SCOPE:   LanguageSwitcher component.
//   DEPENDS: react-i18next (useTranslation), @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4 bilingual UI.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LanguageSwitcher  - ghost button toggling between ru and en
// END_MODULE_MAP

// START_CONTRACT: LanguageSwitcher
//   PURPOSE: Render a small button that flips i18next.language between 'ru'
//            and 'en'.
//   INPUTS:  none.
//   OUTPUTS: JSX — Button labelled with the *target* language.
//   SIDE_EFFECTS: i18n.changeLanguage() — also persists via the configured
//                 LanguageDetector (localStorage cache).
//   LINKS:   ProfilePage also persists language to the server (preferred_language).
// END_CONTRACT: LanguageSwitcher
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
