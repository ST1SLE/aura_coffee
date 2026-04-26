import { useTranslation } from 'react-i18next';

// START_MODULE_CONTRACT
//   PURPOSE: Catch-all 404 page rendered for unknown paths under the Layout
//            route. Pure presentation.
//   SCOPE:   NotFoundPage component.
//   DEPENDS: react-i18next.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   NotFoundPage  - 404 catch-all (pure presentation)
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
