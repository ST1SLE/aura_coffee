import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Orders REST client — checkout creation, customer order detail,
//            history, checkout estimate, cancellation, and repeat-order handoff. Defines a
//            discriminated union for the request payload so pickup vs delivery
//            (saved-address vs inline-address) is enforced statically.
//   SCOPE:   OrderType, OrderStatus, InlineDeliveryAddress, CreateOrderPayload,
//            CheckoutOptions, CheckoutEstimateResponse, OrderItemResponse,
//            OrderResponse, OrderListResponse, RepeatOrderResult, OrderApiError,
//            createOrder, estimateOrder, getOrder, listOrders, cancelOrder,
//            repeatOrder.
//   DEPENDS: M-CORE-API (HTTP /api/v1/orders), ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 checkout;
//            INV-014 (order_items rendered from server snapshots).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OrderType                - 'pickup' | 'delivery'
//   InlineDeliveryAddress    - shape for new (unsaved) delivery address
//   CheckoutOptions          - promo/points/requested-time fields shared by create/estimate
//   CreateOrderPayload       - discriminated union (pickup | delivery+id | delivery+inline)
//   CheckoutEstimateResponse - server-owned checkout totals and delivery guidance
//   OrderStatus              - PDD §6.1 customer-visible order states
//   OrderItemResponse        - immutable server snapshot for one order line
//   OrderResponse            - server response with totals, status, confirmation_url
//   OrderListResponse        - GET /orders?page&per_page response with orders[]
//   RepeatOrderResult        - POST /orders/{id}/repeat result
//   OrderApiError            - Error subclass with status + detail (409 = out-of-radius)
//   createOrder              - POST /orders, returns OrderResponse
//   estimateOrder            - POST /orders/estimate, returns server-owned totals
//   getOrder                 - GET /orders/{id}, returns detail for polling/status
//   listOrders               - GET /orders?page&per_page, returns history
//   cancelOrder              - POST /orders/{id}/cancel, returns updated detail
//   repeatOrder              - POST /orders/{id}/repeat, returns cart rebuild result
// END_MODULE_MAP

export type OrderType = 'pickup' | 'delivery';
export type OrderStatus =
  | 'created'
  | 'paid'
  | 'preparing'
  | 'ready'
  | 'in_delivery'
  | 'completed'
  | 'cancelled';

export interface InlineDeliveryAddress {
  text: string;
  lat?: number | null;
  lon?: number | null;
  apartment?: string | null;
  entrance?: string | null;
  floor?: string | null;
  comment?: string | null;
}

export interface CheckoutOptions {
  promocode_code?: string;
  points_to_use?: number;
  requested_time?: string;
}

// Дискриминированный union — TypeScript гарантирует XOR:
// либо сохранённый (delivery_address_id), либо новый inline (delivery_address).
export type CreateOrderPayload =
  | ({ type: 'pickup' } & CheckoutOptions)
  | ({ type: 'delivery'; delivery_address_id: string } & CheckoutOptions)
  | ({ type: 'delivery'; delivery_address: InlineDeliveryAddress } & CheckoutOptions);

export interface CheckoutEstimateResponse {
  subtotal: number;
  discount_amount: number;
  points_used: number;
  delivery_fee: number;
  total: number;
  estimated_accrual: number;
  estimated_ready_at?: string | null;
  loyalty_balance: number;
  min_delivery_amount: number;
  free_delivery_threshold: number;
  free_delivery_remaining: number;
}

export interface OrderItemResponse {
  id?: string;
  menu_item_id?: number | null;
  menu_item_name_ru: string;
  menu_item_name_en: string;
  size_option_id?: number | null;
  size_label?: string | null;
  unit_price: number;
  modifiers_snapshot: unknown[];
  quantity: number;
  line_total: number;
}

export interface OrderResponse {
  id: string;
  user_id?: string;
  status: OrderStatus;
  type: OrderType;
  items: OrderItemResponse[];
  subtotal: number;
  discount_amount: number;
  points_used?: number;
  delivery_fee: number;
  total: number;
  estimated_accrual?: number;
  confirmation_url?: string | null;
  requested_time?: string | null;
  estimated_ready_at?: string | null;
  cancelled_by?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export interface OrderListResponse {
  orders: OrderResponse[];
  total_count: number;
  page: number;
  per_page: number;
}

export interface RepeatOrderSkippedEntry {
  reason: string;
  message_ru?: string;
  message_en?: string;
}

export interface RepeatOrderResult {
  added_to_cart: number;
  skipped: RepeatOrderSkippedEntry[];
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
    const body = (await res.json()) as { detail?: unknown };
    detail =
      typeof body?.detail === 'string'
        ? body.detail
        : body?.detail
          ? JSON.stringify(body.detail)
          : undefined;
  } catch {
    // non-json body
  }
  return new OrderApiError(res.status, detail);
}

function assertOrder(body: unknown): asserts body is OrderResponse {
  if (
    !body ||
    typeof body !== 'object' ||
    typeof (body as OrderResponse).id !== 'string' ||
    !Array.isArray((body as OrderResponse).items) ||
    typeof (body as OrderResponse).subtotal !== 'number' ||
    typeof (body as OrderResponse).total !== 'number'
  ) {
    throw new OrderApiError(500, 'Invalid order payload');
  }
}

function assertOrderList(body: unknown): asserts body is OrderListResponse {
  if (
    !body ||
    typeof body !== 'object' ||
    !Array.isArray((body as OrderListResponse).orders) ||
    typeof (body as OrderListResponse).total_count !== 'number' ||
    typeof (body as OrderListResponse).page !== 'number' ||
    typeof (body as OrderListResponse).per_page !== 'number'
  ) {
    throw new OrderApiError(500, 'Invalid order history payload');
  }
}

function assertEstimate(body: unknown): asserts body is CheckoutEstimateResponse {
  if (
    !body ||
    typeof body !== 'object' ||
    typeof (body as CheckoutEstimateResponse).subtotal !== 'number' ||
    typeof (body as CheckoutEstimateResponse).discount_amount !== 'number' ||
    typeof (body as CheckoutEstimateResponse).points_used !== 'number' ||
    typeof (body as CheckoutEstimateResponse).delivery_fee !== 'number' ||
    typeof (body as CheckoutEstimateResponse).total !== 'number' ||
    typeof (body as CheckoutEstimateResponse).estimated_accrual !== 'number' ||
    typeof (body as CheckoutEstimateResponse).loyalty_balance !== 'number' ||
    typeof (body as CheckoutEstimateResponse).free_delivery_remaining !==
      'number'
  ) {
    throw new OrderApiError(500, 'Invalid checkout estimate payload');
  }
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
  const body = await res.json();
  assertOrder(body);
  return body;
}

// START_CONTRACT: estimateOrder
//   PURPOSE: Fetch server-owned checkout totals for the current cart and
//            selected checkout options without creating an order.
//   INPUTS:  payload: CreateOrderPayload — same shape as createOrder so the
//            backend validates promo, points, requested_time, and delivery
//            address ownership/radius consistently.
//   OUTPUTS: Promise<CheckoutEstimateResponse> — totals/free-delivery guidance
//            rendered by CheckoutPage.
//   SIDE_EFFECTS: HTTP POST /api/v1/orders/estimate (authenticated). Throws
//                 OrderApiError. INV-013 — payload may contain address PII; UI
//                 must not log raw payload. Money values are display-only.
//   LINKS:   PDD §7.2, §7.4, §7.5; CheckoutPage renders the response as-is.
// END_CONTRACT: estimateOrder
export async function estimateOrder(
  payload: CreateOrderPayload,
): Promise<CheckoutEstimateResponse> {
  const res = await authenticatedFetch('/api/v1/orders/estimate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertEstimate(body);
  return body;
}

// START_CONTRACT: getOrder
//   PURPOSE: Fetch own-order detail for payment confirmation_url polling and
//            status freshness rendering.
//   INPUTS:  orderId: string — UUID from route or checkout response.
//   OUTPUTS: Promise<OrderResponse> — server-owned totals/items/status.
//   SIDE_EFFECTS: HTTP GET /api/v1/orders/{id} (authenticated). Throws
//                 OrderApiError on non-2xx or payload drift.
//   LINKS:   PDD §4.4, §6.1; OrderDetailPage polls through this method.
// END_CONTRACT: getOrder
export async function getOrder(orderId: string): Promise<OrderResponse> {
  const res = await authenticatedFetch(`/api/v1/orders/${orderId}`);
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertOrder(body);
  return body;
}

// START_CONTRACT: listOrders
//   PURPOSE: Fetch the customer's paginated order history.
//   INPUTS:  page: number — 1-based page index
//            perPage: number — backend page size.
//   OUTPUTS: Promise<OrderListResponse> — orders[] + pagination metadata.
//   SIDE_EFFECTS: HTTP GET /api/v1/orders?page&per_page (authenticated).
//   LINKS:   PDD §4.4, §7.7; OrdersPage renders this response as-is.
// END_CONTRACT: listOrders
export async function listOrders(
  page = 1,
  perPage = 20,
): Promise<OrderListResponse> {
  const res = await authenticatedFetch(
    `/api/v1/orders?page=${page}&per_page=${perPage}`,
  );
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertOrderList(body);
  return body;
}

// START_CONTRACT: cancelOrder
//   PURPOSE: Request customer cancellation for a PAID own-order.
//   INPUTS:  orderId: string — UUID to cancel.
//   OUTPUTS: Promise<OrderResponse> — updated server order detail.
//   SIDE_EFFECTS: HTTP POST /api/v1/orders/{id}/cancel. Backend owns INV-004
//                 refund/loyalty transactionality; UI only offers the action
//                 when status=paid.
//   LINKS:   PDD §6.1, §7.6, INV-005.
// END_CONTRACT: cancelOrder
export async function cancelOrder(orderId: string): Promise<OrderResponse> {
  const res = await authenticatedFetch(`/api/v1/orders/${orderId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: null }),
  });
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  assertOrder(body);
  return body;
}

// START_CONTRACT: repeatOrder
//   PURPOSE: Rebuild the customer's cart from a historical order using current
//            menu availability and prices.
//   INPUTS:  orderId: string — UUID to repeat.
//   OUTPUTS: Promise<RepeatOrderResult> — added count + skipped entries.
//   SIDE_EFFECTS: HTTP POST /api/v1/orders/{id}/repeat; backend rewrites Redis cart.
//   LINKS:   PDD §7.7, INV-014.
// END_CONTRACT: repeatOrder
export async function repeatOrder(orderId: string): Promise<RepeatOrderResult> {
  const res = await authenticatedFetch(`/api/v1/orders/${orderId}/repeat`, {
    method: 'POST',
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as RepeatOrderResult;
}
