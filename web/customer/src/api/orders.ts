import { authenticatedFetch } from './client';

export type OrderType = 'PICKUP' | 'DELIVERY';

export interface InlineDeliveryAddress {
  text: string;
  lat?: number | null;
  lon?: number | null;
  apartment?: string | null;
  entrance?: string | null;
  floor?: string | null;
  comment?: string | null;
}

// Дискриминированный union — TypeScript гарантирует XOR:
// либо сохранённый (delivery_address_id), либо новый inline (delivery_address).
export type CreateOrderPayload =
  | { type: 'PICKUP' }
  | { type: 'DELIVERY'; delivery_address_id: string }
  | { type: 'DELIVERY'; delivery_address: InlineDeliveryAddress };

export interface OrderResponse {
  id: string;
  status: string;
  type: OrderType;
  items: unknown[];
  subtotal: number;
  discount_amount: number;
  points_used: number;
  delivery_fee: number;
  total: number;
  estimated_accrual: number;
  confirmation_url?: string | null;
  requested_time?: string | null;
  estimated_ready_at?: string | null;
  cancelled_by?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export class OrderApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'OrderApiError';
  }
}

async function parseError(res: Response): Promise<OrderApiError> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: string };
    detail = body?.detail;
  } catch {
    // non-json body
  }
  return new OrderApiError(res.status, detail);
}

export async function createOrder(
  payload: CreateOrderPayload,
): Promise<OrderResponse> {
  const res = await authenticatedFetch('/api/v1/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as OrderResponse;
}
