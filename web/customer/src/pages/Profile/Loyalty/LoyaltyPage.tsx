import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  getLoyaltyBalance,
  listLoyaltyTransactions,
  type LoyaltyBalance,
  type LoyaltyTransaction,
} from '@/api/loyalty';
import { TransactionRow } from './TransactionRow';

// START_MODULE_CONTRACT
//   PURPOSE: /profile/loyalty route — show loyalty balance + lifetime accrued
//            and a paginated transaction history loaded one page at a time
//            (page size 20). Independent error states for balance vs history.
//   SCOPE:   LoyaltyPage component.
//   DEPENDS: react, react-i18next, @/components/ui/button, @/api/loyalty
//            (getLoyaltyBalance, listLoyaltyTransactions), ./TransactionRow.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §9 loyalty.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoyaltyPage  - /profile/loyalty — balance card + paginated transactions
// END_MODULE_MAP

const PER_PAGE = 20;

// START_CONTRACT: LoyaltyPage
//   PURPOSE: Render loyalty balance and paginate the transaction history.
//   INPUTS:  none.
//   OUTPUTS: JSX — header card with balance + history section with rows.
//   SIDE_EFFECTS: HTTP getLoyaltyBalance() and listLoyaltyTransactions(1, 20)
//                 on mount; further pages on "load more" click. Empty-page
//                 heuristic decides hasMore.
//   LINKS:   PDD §9; TransactionRow renders each entry.
// END_CONTRACT: LoyaltyPage
export function LoyaltyPage() {
  const { t } = useTranslation();

  const [balance, setBalance] = useState<LoyaltyBalance | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [balanceLoading, setBalanceLoading] = useState(true);

  const [items, setItems] = useState<LoyaltyTransaction[]>([]);
  const [page, setPage] = useState(0); // последняя загруженная страница
  const [hasMore, setHasMore] = useState(true);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState<string | null>(null);

  async function loadPage(nextPage: number) {
    setTxLoading(true);
    setTxError(null);
    try {
      const res = await listLoyaltyTransactions(nextPage, PER_PAGE);
      setItems((prev) => (nextPage === 1 ? res.items : [...prev, ...res.items]));
      setPage(nextPage);
      // Следующая страница есть только если текущая была полной.
      setHasMore(res.items.length === PER_PAGE);
    } catch {
      setTxError(t('pages.profile.loadError'));
    } finally {
      setTxLoading(false);
    }
  }

  useEffect(() => {
    void (async () => {
      setBalanceLoading(true);
      try {
        setBalance(await getLoyaltyBalance());
      } catch {
        setBalanceError(t('pages.profile.loadError'));
      } finally {
        setBalanceLoading(false);
      }
    })();
    void loadPage(1);
    // Загружаем один раз на mount; зависимости из t/i18n не нужны.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="text-center">
        <h1 className="text-sm font-medium text-muted-foreground">
          {t('pages.loyalty.title')}
        </h1>
        {balanceLoading ? (
          <div className="flex justify-center py-6">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-foreground" />
          </div>
        ) : balance ? (
          <>
            <div className="mt-2 flex items-baseline justify-center gap-2">
              <span className="text-5xl font-bold">{balance.balance}</span>
              <span className="text-lg text-muted-foreground">
                {t('pages.loyalty.balance_label')}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {t('pages.loyalty.lifetime_label', {
                value: balance.lifetime_accrued,
              })}
            </p>
          </>
        ) : balanceError ? (
          <p className="mt-2 text-sm text-destructive">{balanceError}</p>
        ) : null}
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">
          {t('pages.loyalty.history_title')}
        </h2>

        {txError && <p className="mb-2 text-sm text-destructive">{txError}</p>}

        {items.length === 0 && !txLoading ? (
          <p className="text-sm text-muted-foreground">
            {t('pages.loyalty.empty')}
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((tx) => (
              <TransactionRow key={tx.id} tx={tx} />
            ))}
          </ul>
        )}

        {hasMore && items.length > 0 && (
          <div className="mt-4 flex justify-center">
            <Button
              variant="outline"
              onClick={() => loadPage(page + 1)}
              disabled={txLoading}
            >
              {t('pages.loyalty.load_more')}
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
