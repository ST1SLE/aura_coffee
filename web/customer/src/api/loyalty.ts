import { authenticatedFetch } from './client';

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

export async function getLoyaltyBalance(): Promise<LoyaltyBalance> {
  const res = await authenticatedFetch('/api/v1/profile/loyalty');
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertBalance(body);
  return body;
}

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
