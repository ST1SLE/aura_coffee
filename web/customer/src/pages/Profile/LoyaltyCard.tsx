import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getLoyaltyBalance, type LoyaltyBalance } from '@/api/loyalty';

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
    <div className="rounded-md border p-4">
      <div className="mb-2 text-sm font-medium text-muted-foreground">
        {t('pages.profile.loyaltyCard.title')}
      </div>
      {error ? (
        <p className="text-sm text-destructive">
          {t('pages.profile.loadError')}
        </p>
      ) : balance ? (
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold">{balance.balance}</span>
          <span className="text-sm text-muted-foreground">
            {t('pages.profile.loyaltyCard.balance_suffix')}
          </span>
        </div>
      ) : (
        <div className="h-8 w-20 animate-pulse rounded bg-muted" />
      )}
      <Link
        to="/profile/loyalty"
        className="mt-2 inline-block text-sm text-primary underline"
      >
        {t('pages.profile.loyaltyCard.view_history')}
      </Link>
    </div>
  );
}
