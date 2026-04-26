import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Toggle button that flips the active i18next language between
//            'ru' and 'en', persisted via the LanguageDetector localStorage cache.
//   SCOPE:   Rendered in Layout header and CourierShell header.
//   DEPENDS: react-i18next, @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (bilingual RU/EN).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LanguageSwitcher - button that toggles i18n.language between ru/en
// END_MODULE_MAP

// START_CONTRACT: LanguageSwitcher
//   PURPOSE: Render a small button that toggles the active i18n language.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element
//   SIDE_EFFECTS: i18n.changeLanguage() — triggers re-render of all t() consumers
//            and persists the preference via the LanguageDetector cache.
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
