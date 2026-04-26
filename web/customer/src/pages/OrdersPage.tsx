import { useTranslation } from 'react-i18next';

// START_MODULE_CONTRACT
//   PURPOSE: Placeholder /orders route — currently just renders title +
//            description from i18n. Will become the real order history /
//            tracking UI in a future phase (PDD §7 status freshness).
//            Pure presentation today.
//   SCOPE:   OrdersPage component.
//   DEPENDS: react-i18next.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 order tracking.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrdersPage  - /orders placeholder (pure presentation)
// END_MODULE_MAP

export function OrdersPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.orders.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.orders.description')}</p>
    </div>
  );
}
