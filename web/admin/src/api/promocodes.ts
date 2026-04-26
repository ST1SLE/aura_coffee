// Типы зеркалят Pydantic-схемы из
// services/core-api/src/core_api/schemas/promocode.py.
// Пока zod в стеке web/admin нет — используем plain TS-интерфейсы,
// как в api/menu.ts. Runtime-валидация выполняется на сервере.

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin promocode endpoints — list/get/create/update/
//            activate/deactivate — plus rubles<>kopecks/percent wire conversion
//            and FastAPI 422 flat-error parser.
//   SCOPE:   Wraps /api/v1/admin/promocodes/*; UI works in rubles, server stores kopecks.
//   DEPENDS: ./client (authenticatedFetch, ApiError).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6 promocodes,
//            INV-002 (admin scope).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError                  - re-export
//   PromocodeDiscountType     - 'percent' | 'fixed_amount'
//   PromocodeState            - inactive/active/expired/exhausted
//   PromocodeStateFilter      - PromocodeState | 'all'
//   PromocodeResponse         - server response shape (kopecks for fixed_amount)
//   PromocodeListResponse     - paginated list
//   PromocodeCreateInput      - UI-level create (rubles + percent integers)
//   PromocodeUpdateInput      - UI-level partial update
//   ListPromocodesParams      - state/code/page/per_page params
//   listPromocodes            - GET list
//   getPromocode              - GET one
//   createPromocode           - POST (translates rubles→kopecks)
//   updatePromocode           - PATCH (translates rubles→kopecks)
//   activatePromocode         - POST /activate (admin only)
//   deactivatePromocode       - POST /deactivate (admin only)
//   parseFieldErrors          - 422 detail → {field: msg} map
// END_MODULE_MAP

export { ApiError };

// ── Enums / literals ─────────────────────────────────────────────────────────

export type PromocodeDiscountType = 'percent' | 'fixed_amount';

export type PromocodeState = 'inactive' | 'active' | 'expired' | 'exhausted';

export type PromocodeStateFilter = PromocodeState | 'all';

// ── Response shapes ──────────────────────────────────────────────────────────

export interface PromocodeResponse {
  id: string;
  code: string;
  discount_type: PromocodeDiscountType;
  // Для percent — целое число 1..100; для fixed_amount — копейки.
  discount_value: number;
  min_order_amount: number;
  valid_from: string | null;
  valid_until: string | null;
  max_uses: number | null;
  max_uses_per_user: number | null;
  current_uses: number;
  is_active: boolean;
  state: PromocodeState;
  created_at: string;
  updated_at?: string | null;
}

export interface PromocodeListResponse {
  items: PromocodeResponse[];
  page: number;
  per_page: number;
  total: number;
}

// ── Input shapes (UI-level, rubles) ──────────────────────────────────────────

// UI передаёт рубли; конверсия rubles → kopecks происходит перед отправкой
// для discount_type='fixed_amount' и для min_order_amount.
// Для discount_type='percent' discount_value_rubles = целое число процентов.

export interface PromocodeCreateInput {
  code: string;
  discount_type: PromocodeDiscountType;
  discount_value_rubles: number;
  min_order_rubles: number | null;
  valid_from: string | null;
  valid_until: string | null;
  max_uses: number | null;
  max_uses_per_user: number | null;
}

export interface PromocodeUpdateInput {
  code?: string;
  discount_type?: PromocodeDiscountType;
  discount_value_rubles?: number;
  min_order_rubles?: number | null;
  valid_from?: string | null;
  valid_until?: string | null;
  max_uses?: number | null;
  max_uses_per_user?: number | null;
}

// ── Wire shapes (kopecks, for server) ────────────────────────────────────────

interface PromocodeCreateWire {
  code: string;
  discount_type: PromocodeDiscountType;
  discount_value: number;
  min_order_amount?: number;
  valid_from?: string | null;
  valid_until?: string | null;
  max_uses?: number | null;
  max_uses_per_user?: number | null;
}

// ── helpers ──────────────────────────────────────────────────────────────────

function toDiscountWire(
  discountType: PromocodeDiscountType,
  rubles: number,
): number {
  if (discountType === 'percent') return Math.round(rubles);
  return Math.round(rubles * 100);
}

function toKopecks(rubles: number): number {
  return Math.round(rubles * 100);
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: 'POST' };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  return json<T>(path, init);
}

function patch<T>(path: string, body: unknown): Promise<T> {
  return json<T>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// ── Query-string builder ─────────────────────────────────────────────────────

export interface ListPromocodesParams {
  state?: PromocodeStateFilter;
  code?: string;
  page?: number;
  per_page?: number;
}

function buildListQuery(params: ListPromocodesParams | undefined): string {
  if (!params) return '';
  const usp = new URLSearchParams();
  if (params.state && params.state !== 'all') usp.set('state', params.state);
  if (params.code) usp.set('code', params.code);
  if (params.page != null) usp.set('page', String(params.page));
  if (params.per_page != null) usp.set('per_page', String(params.per_page));
  const qs = usp.toString();
  return qs ? `?${qs}` : '';
}

// ── API functions ────────────────────────────────────────────────────────────

// START_CONTRACT: listPromocodes
//   PURPOSE: Fetch paginated promocode list with optional state filter and code search.
//   INPUTS:  params?: ListPromocodesParams — state='all' omits the param.
//   OUTPUTS: Promise<PromocodeListResponse>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002.
// END_CONTRACT: listPromocodes
export const listPromocodes = (
  params?: ListPromocodesParams,
): Promise<PromocodeListResponse> =>
  json(`/api/v1/admin/promocodes${buildListQuery(params)}`);

// START_CONTRACT: getPromocode
//   PURPOSE: Fetch a single promocode by id.
//   INPUTS:  id: string
//   OUTPUTS: Promise<PromocodeResponse>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002.
// END_CONTRACT: getPromocode
export const getPromocode = (id: string): Promise<PromocodeResponse> =>
  json(`/api/v1/admin/promocodes/${id}`);

// START_CONTRACT: createPromocode
//   PURPOSE: Create a new promocode (admin only). Translates UI rubles to wire
//            kopecks for fixed_amount and rounds percent values to integers.
//   INPUTS:  input: PromocodeCreateInput
//   OUTPUTS: Promise<PromocodeResponse>
//   SIDE_EFFECTS: POST; 409 on duplicate code, 422 on validation.
//   LINKS:   INV-002.
// END_CONTRACT: createPromocode
export const createPromocode = (
  input: PromocodeCreateInput,
): Promise<PromocodeResponse> => {
  const wire: PromocodeCreateWire = {
    code: input.code,
    discount_type: input.discount_type,
    discount_value: toDiscountWire(input.discount_type, input.discount_value_rubles),
  };
  if (input.min_order_rubles != null) wire.min_order_amount = toKopecks(input.min_order_rubles);
  if (input.valid_from !== undefined) wire.valid_from = input.valid_from;
  if (input.valid_until !== undefined) wire.valid_until = input.valid_until;
  if (input.max_uses !== undefined) wire.max_uses = input.max_uses;
  if (input.max_uses_per_user !== undefined) wire.max_uses_per_user = input.max_uses_per_user;
  return post('/api/v1/admin/promocodes', wire);
};

// START_CONTRACT: updatePromocode
//   PURPOSE: Partial-update a promocode (admin only). Wire conversion mirrors
//            createPromocode but only for fields actually present in input.
//            Server may reject if current_uses > 0 (locked fields).
//   INPUTS:  id: string, input: PromocodeUpdateInput
//   OUTPUTS: Promise<PromocodeResponse>
//   SIDE_EFFECTS: PATCH; 422 with field_locked_after_use possible.
//   LINKS:   INV-002.
// END_CONTRACT: updatePromocode
export const updatePromocode = (
  id: string,
  input: PromocodeUpdateInput,
): Promise<PromocodeResponse> => {
  const wire: Record<string, unknown> = {};
  if (input.code !== undefined) wire.code = input.code;
  if (input.discount_type !== undefined) wire.discount_type = input.discount_type;
  if (input.discount_value_rubles !== undefined) {
    const dt = input.discount_type ?? 'fixed_amount';
    wire.discount_value = toDiscountWire(dt, input.discount_value_rubles);
  }
  if (input.min_order_rubles !== undefined) {
    wire.min_order_amount = input.min_order_rubles == null ? null : toKopecks(input.min_order_rubles);
  }
  if (input.valid_from !== undefined) wire.valid_from = input.valid_from;
  if (input.valid_until !== undefined) wire.valid_until = input.valid_until;
  if (input.max_uses !== undefined) wire.max_uses = input.max_uses;
  if (input.max_uses_per_user !== undefined) wire.max_uses_per_user = input.max_uses_per_user;
  return patch(`/api/v1/admin/promocodes/${id}`, wire);
};

// START_CONTRACT: activatePromocode
//   PURPOSE: Flip is_active=true on a promocode (admin only). Server rejects
//            with 409 if expired/exhausted.
//   INPUTS:  id: string
//   OUTPUTS: Promise<PromocodeResponse>
//   SIDE_EFFECTS: POST; 409 on terminal state.
//   LINKS:   INV-002.
// END_CONTRACT: activatePromocode
export const activatePromocode = (id: string): Promise<PromocodeResponse> =>
  post(`/api/v1/admin/promocodes/${id}/activate`);

// START_CONTRACT: deactivatePromocode
//   PURPOSE: Flip is_active=false on a promocode (admin only).
//   INPUTS:  id: string
//   OUTPUTS: Promise<PromocodeResponse>
//   SIDE_EFFECTS: POST.
//   LINKS:   INV-002.
// END_CONTRACT: deactivatePromocode
export const deactivatePromocode = (id: string): Promise<PromocodeResponse> =>
  post(`/api/v1/admin/promocodes/${id}/deactivate`);

// ── Error parsing ────────────────────────────────────────────────────────────

// Преобразует FastAPI 422 body в { <field>: <msg> } для показа field-level
// ошибок в форме. Server может прислать msg-код вида "field_locked_after_use"
// или обычный текст; рендер выбирает локализованное сообщение по совпадению.

// START_CONTRACT: parseFieldErrors
//   PURPOSE: Convert a FastAPI 422 ApiError into a flat {field: msg} map keyed
//            by the last segment of `loc`, matching the form-state field names.
//            Server may return code-style msgs (e.g. 'field_locked_after_use')
//            which the form localizes by lookup.
//   INPUTS:  err: unknown
//   OUTPUTS: Record<string, string> — empty if not ApiError or no detail.
//   SIDE_EFFECTS: none.
// END_CONTRACT: parseFieldErrors
export function parseFieldErrors(err: unknown): Record<string, string> {
  if (!(err instanceof ApiError)) return {};
  const body = err.body as
    | { detail?: Array<{ loc?: unknown[]; msg?: string }> }
    | null
    | undefined;
  if (!body?.detail || !Array.isArray(body.detail)) return {};
  const out: Record<string, string> = {};
  for (const d of body.detail) {
    if (!Array.isArray(d.loc) || typeof d.msg !== 'string') continue;
    const field = d.loc[d.loc.length - 1];
    if (typeof field === 'string') out[field] = d.msg;
  }
  return out;
}
