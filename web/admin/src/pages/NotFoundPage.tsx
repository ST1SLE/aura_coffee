import { useTranslation } from 'react-i18next';

// START_MODULE_CONTRACT
//   PURPOSE: Catch-all 404 page rendered by the router for unknown paths.
//            Pure presentation — only uses i18n for localized text.
//   SCOPE:   Mounted as the trailing "*" route in App.tsx.
//   DEPENDS: react-i18next.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   NotFoundPage - localized 404 message
// END_MODULE_MAP

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.notFound.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.notFound.description')}</p>
    </div>
  );
}
