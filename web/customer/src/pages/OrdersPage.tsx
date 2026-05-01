import { useTranslation } from 'react-i18next';
import { ReceiptText } from 'lucide-react';

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
    <div className="mx-auto max-w-3xl px-4 py-5 md:px-6">
      <div className="aura-surface flex min-h-[45vh] flex-col items-center justify-center rounded-lg p-6 text-center">
        <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-primary">
          <ReceiptText className="h-6 w-6" aria-hidden="true" />
        </span>
        <h1 className="text-3xl font-semibold tracking-normal">
          {t('pages.orders.title')}
        </h1>
        <p className="mt-2 text-muted-foreground">
          {t('pages.orders.description')}
        </p>
      </div>
    </div>
  );
}
