import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { LoyaltyTransaction } from '@/api/loyalty';

// START_MODULE_CONTRACT
//   PURPOSE: One row in the loyalty history list — formatted date, type label,
//            optional description + order link, signed amount, and
//            balance-after. No state, just formatting helpers.
//   SCOPE:   TransactionRow component (private helpers shortId / amountClass /
//            formatAmount / formatDate are not exported).
//   DEPENDS: react-router-dom (Link), react-i18next, @/api/loyalty types.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §9 loyalty history.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   TransactionRow  - one ledger row in the loyalty history (pure presentation)
// END_MODULE_MAP

interface Props {
  tx: LoyaltyTransaction;
}

// Короткий UUID — первые 8 символов, как в customer-orders-ui.
function shortId(id: string): string {
  return id.slice(0, 8);
}

function amountClass(amount: number): string {
  if (amount > 0) return 'text-green-600';
  if (amount < 0) return 'text-red-600';
  return 'text-foreground';
}

function formatAmount(amount: number): string {
  if (amount > 0) return `+${amount}`;
  return String(amount);
}

function formatDate(iso: string, locale: string): string {
  try {
    return new Date(iso).toLocaleDateString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export function TransactionRow({ tx }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === 'ru' ? 'ru-RU' : 'en-US';

  const typeLabel = t(`pages.loyalty.txType.${tx.type}`, { defaultValue: tx.type });

  return (
    <li className="flex items-start justify-between gap-3 rounded-md border p-3 text-sm">
      <div className="flex flex-col">
        <span className="text-xs text-muted-foreground">
          {formatDate(tx.created_at, locale)}
        </span>
        <span className="font-medium">{typeLabel}</span>
      </div>

      <div className="flex flex-1 flex-col px-2">
        {tx.description && (
          <span className="text-xs text-muted-foreground">{tx.description}</span>
        )}
        {tx.order_id && (
          <Link
            to={`/orders/${tx.order_id}`}
            className="text-xs text-primary underline"
          >
            {t('pages.loyalty.txRow.order_link', { id: shortId(tx.order_id) })}
          </Link>
        )}
      </div>

      <div className="flex flex-col items-end">
        <span className={`text-lg font-semibold ${amountClass(tx.amount)}`}>
          {formatAmount(tx.amount)}
        </span>
        <span className="text-xs text-muted-foreground">
          {t('pages.loyalty.txRow.balance_after', { value: tx.balance_after })}
        </span>
      </div>
    </li>
  );
}
