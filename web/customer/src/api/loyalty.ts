import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Loyalty REST client — balance + paginated transaction history.
//            Includes runtime shape assertions to catch contract drift between
//            this client and core-api.
//   SCOPE:   LoyaltyTransactionType / LoyaltyBalance / LoyaltyTransaction /
//            LoyaltyTransactionsPage DTOs, LoyaltyApiError, getLoyaltyBalance,
//            listLoyaltyTransactions.
//   DEPENDS: M-CORE-API (HTTP /api/v1/profile/loyalty[/transactions]),
//            ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §9 loyalty.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoyaltyTransactionType     - union of accrual/redemption/reversal/etc.
//   LoyaltyBalance             - { balance, lifetime_accrued }
//   LoyaltyTransaction         - one ledger row (id, amount, balance_after, …)
//   LoyaltyTransactionsPage    - paginated wrapper
//   LoyaltyApiError            - Error subclass with HTTP status + detail
//   getLoyaltyBalance          - GET /profile/loyalty
//   listLoyaltyTransactions    - GET /profile/loyalty/transactions?page&per_page
// END_MODULE_MAP

export type LoyaltyTransactionType =
  | 'accrual'
  | 'redemption'
  | 'reversal'
  | 'reservation'
  | 'admin_adjustment';

export interface LoyaltyBalance {
  balance: number;
  lifetime_accrued: number;
}

export interface LoyaltyTransaction {
  id: string;
  order_id: string | null;
  type: LoyaltyTransactionType;
  amount: number;
  balance_after: number;
  description: string | null;
  created_at: string;
}

export interface LoyaltyTransactionsPage {
  items: LoyaltyTransaction[];
  page: number;
  per_page: number;
  total: number;
}

// START_CONTRACT: LoyaltyApiError
//   PURPOSE: Error subclass carrying HTTP status + server-provided detail so the
//            UI can show a friendly message and (optionally) branch on status.
//   INPUTS:  status: number
//            detail?: string
//   OUTPUTS: LoyaltyApiError instance.
//   SIDE_EFFECTS: none.
// END_CONTRACT: LoyaltyApiError
export class LoyaltyApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'LoyaltyApiError';
  }
}

async function parseError(res: Response): Promise<LoyaltyApiError> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: string };
    detail = body?.detail;
  } catch {
    // non-json body
  }
  return new LoyaltyApiError(res.status, detail);
}

// Минимальная runtime-валидация: защищаемся от несовпадения контракта с бекендом.
function assertBalance(body: unknown): asserts body is LoyaltyBalance {
  if (
    !body ||
    typeof body !== 'object' ||
    typeof (body as LoyaltyBalance).balance !== 'number' ||
    typeof (body as LoyaltyBalance).lifetime_accrued !== 'number'
  ) {
    throw new LoyaltyApiError(500, 'Invalid loyalty balance payload');
  }
}

function assertTransactionsPage(
  body: unknown,
): asserts body is LoyaltyTransactionsPage {
  if (
    !body ||
    typeof body !== 'object' ||
    !Array.isArray((body as LoyaltyTransactionsPage).items) ||
    typeof (body as LoyaltyTransactionsPage).page !== 'number' ||
    typeof (body as LoyaltyTransactionsPage).per_page !== 'number' ||
    typeof (body as LoyaltyTransactionsPage).total !== 'number'
  ) {
    throw new LoyaltyApiError(500, 'Invalid loyalty transactions payload');
  }
}

// START_CONTRACT: getLoyaltyBalance
//   PURPOSE: Fetch current loyalty balance and lifetime accrued total.
//   INPUTS:  none.
//   OUTPUTS: Promise<LoyaltyBalance>.
//   SIDE_EFFECTS: HTTP GET /api/v1/profile/loyalty (authenticated). Throws
//                 LoyaltyApiError(500, 'Invalid loyalty balance payload') on
//                 schema mismatch, or LoyaltyApiError(status) on non-2xx.
//   LINKS:   PDD §9.1 loyalty balance; LoyaltyCard / LoyaltyPage consumers.
// END_CONTRACT: getLoyaltyBalance
export async function getLoyaltyBalance(): Promise<LoyaltyBalance> {
  const res = await authenticatedFetch('/api/v1/profile/loyalty');
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertBalance(body);
  return body;
}

// START_CONTRACT: listLoyaltyTransactions
//   PURPOSE: Fetch one page of loyalty ledger entries.
//   INPUTS:  page: number     — 1-based page number
//            per_page: number — page size
//   OUTPUTS: Promise<LoyaltyTransactionsPage> — items + page + per_page + total.
//   SIDE_EFFECTS: HTTP GET /api/v1/profile/loyalty/transactions?page&per_page;
//                 throws LoyaltyApiError on non-2xx or schema mismatch.
//   LINKS:   PDD §9.2 history; LoyaltyPage paginates with hasMore heuristic.
// END_CONTRACT: listLoyaltyTransactions
export async function listLoyaltyTransactions(
  page: number,
  per_page: number,
): Promise<LoyaltyTransactionsPage> {
  const res = await authenticatedFetch(
    `/api/v1/profile/loyalty/transactions?page=${page}&per_page=${per_page}`,
  );
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertTransactionsPage(body);
  return body;
}
