import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getLoyaltyBalance, type LoyaltyBalance } from '@/api/loyalty';

// START_MODULE_CONTRACT
//   PURPOSE: Compact loyalty-balance card mounted inside ProfilePage — fetches
//            the balance on mount and shows it next to a link to the full
//            history at /profile/loyalty.
//   SCOPE:   LoyaltyCard component.
//   DEPENDS: react, react-router-dom (Link), react-i18next, @/api/loyalty
//            (getLoyaltyBalance).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §9 loyalty surface.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoyaltyCard  - small loyalty balance card with link to full history
// END_MODULE_MAP

// START_CONTRACT: LoyaltyCard
//   PURPOSE: Fetch and display the user's loyalty balance in a card with a
//            link to the full ledger.
//   INPUTS:  none.
//   OUTPUTS: JSX — card with skeleton / value / error states + history link.
//   SIDE_EFFECTS: HTTP getLoyaltyBalance() on mount.
//   LINKS:   PDD §9; LoyaltyPage renders the full history.
// END_CONTRACT: LoyaltyCard
export function LoyaltyCard() {
  const { t } = useTranslation();
  const [balance, setBalance] = useState<LoyaltyBalance | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setBalance(await getLoyaltyBalance());
      } catch {
        setError(true);
      }
    })();
  }, []);

  return (
    <div className="aura-surface rounded-lg p-4">
      <div className="mb-2 text-sm font-medium text-muted-foreground">
        {t('pages.profile.loyaltyCard.title')}
      </div>
      {error ? (
        <p className="text-sm text-destructive">
          {t('pages.profile.loadError')}
        </p>
      ) : balance ? (
        <div className="flex items-baseline gap-2">
          <span className="aura-numeric text-4xl font-bold text-primary">
            {balance.balance}
          </span>
          <span className="text-sm text-muted-foreground">
            {t('pages.profile.loyaltyCard.balance_suffix')}
          </span>
        </div>
      ) : (
        <div className="h-8 w-20 animate-pulse rounded-md bg-muted" />
      )}
      <Link
        to="/profile/loyalty"
        className="mt-3 inline-block font-display text-sm font-semibold text-primary underline"
      >
        {t('pages.profile.loyaltyCard.view_history')}
      </Link>
    </div>
  );
}
