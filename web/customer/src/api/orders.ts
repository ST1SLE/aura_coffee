import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Orders REST client — POST /api/v1/orders for checkout. Defines a
//            discriminated union for the request payload so PICKUP vs DELIVERY
//            (saved-address vs inline-address) is enforced statically.
//   SCOPE:   OrderType, InlineDeliveryAddress, CreateOrderPayload, OrderResponse,
//            OrderApiError, createOrder.
//   DEPENDS: M-CORE-API (HTTP /api/v1/orders), ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 checkout;
//            INV-014 (order_items rendered from server snapshots).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrderType                - 'PICKUP' | 'DELIVERY'
//   InlineDeliveryAddress    - shape for new (unsaved) delivery address
//   CreateOrderPayload       - discriminated union (PICKUP | DELIVERY+id | DELIVERY+inline)
//   OrderResponse            - server response with totals, status, confirmation_url
//   OrderApiError            - Error subclass with status + detail (409 = out-of-radius)
//   createOrder              - POST /orders, returns OrderResponse
// END_MODULE_MAP

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

// START_CONTRACT: OrderApiError
//   PURPOSE: Carry HTTP status + server detail so CheckoutPage can render the
//            localized 409 out-of-radius message and other failures.
//   INPUTS:  status: number
//            detail?: string
//   OUTPUTS: OrderApiError instance.
//   SIDE_EFFECTS: none.
// END_CONTRACT: OrderApiError
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

// START_CONTRACT: createOrder
//   PURPOSE: Submit a checkout payload — pickup or delivery (saved or inline).
//   INPUTS:  payload: CreateOrderPayload — discriminated union; TypeScript
//            enforces XOR between delivery_address_id and delivery_address.
//   OUTPUTS: Promise<OrderResponse> — order id + totals + status (+ confirmation_url
//            when payment redirect is required).
//   SIDE_EFFECTS: HTTP POST /api/v1/orders (authenticated); throws OrderApiError.
//                 INV-013 — payload contains PII (address, optional comment); UI
//                 must not log raw payload. INV-014 — server returns
//                 snapshot-shaped items[]; UI renders as-is, never recomputes prices.
//   LINKS:   PDD §7 checkout; CheckoutPage is the only caller.
// END_CONTRACT: createOrder
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
