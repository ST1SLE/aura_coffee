import { useTranslation } from 'react-i18next';

// START_MODULE_CONTRACT
//   PURPOSE: Placeholder/stub CartPage from earlier scaffolding. The active
//            cart route mounts pages/Cart/CartPage.tsx (see App.tsx import).
//            Kept for now to avoid widening this retrofit's diff; remove in a
//            follow-up cleanup. Pure presentation.
//   SCOPE:   CartPage component (stub).
//   DEPENDS: react-i18next.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER. Not registered in
//            App.tsx — the real one is pages/Cart/CartPage.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CartPage  - placeholder stub (pure presentation)
// END_MODULE_MAP

export function CartPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="text-2xl font-bold">{t('pages.cart.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('pages.cart.description')}</p>
    </div>
  );
}
