import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: CRUD client for /api/v1/profile/addresses — list/create/update/
//            delete saved delivery addresses, and a setDefaultAddress helper
//            that PATCHes is_default=true (server has no dedicated endpoint).
//   SCOPE:   AddressResponse / AddressCreatePayload / AddressUpdatePayload DTOs,
//            AddressApiError class, listAddresses, createAddress, updateAddress,
//            deleteAddress, setDefaultAddress.
//   DEPENDS: M-CORE-API (HTTP /api/v1/profile/addresses), ./client
//            (authenticatedFetch — Bearer + 401 retry).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7 delivery addresses,
//            INV-013 (address text/coords are PII; UI must not log raw values).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AddressResponse        - server-side address record (id + payload + is_default)
//   AddressCreatePayload   - body for POST /addresses (label required server-side)
//   AddressUpdatePayload   - partial body for PATCH /addresses/:id
//   AddressApiError        - Error subclass with HTTP status (used for 409 radius)
//   listAddresses          - GET all addresses for the current user
//   createAddress          - POST a new address
//   updateAddress          - PATCH partial fields on an existing address
//   deleteAddress          - DELETE an address by id
//   setDefaultAddress      - PATCH is_default=true (no dedicated endpoint)
// END_MODULE_MAP

export interface AddressResponse {
  id: string;
  address_text: string;
  lat: number | null;
  lon: number | null;
  label: string | null;
  apartment: string | null;
  entrance: string | null;
  floor: string | null;
  comment: string | null;
  is_default: boolean;
}

export interface AddressCreatePayload {
  label: string;
  address_text: string;
  lat: number | null;
  lon: number | null;
  apartment: string | null;
  entrance: string | null;
  floor: string | null;
  comment: string | null;
}

export type AddressUpdatePayload = Partial<
  Omit<AddressCreatePayload, 'lat' | 'lon'>
> & {
  is_default?: boolean;
};

// START_CONTRACT: AddressApiError
//   PURPOSE: Carry HTTP status + server detail so the UI can branch on 409
//            (out-of-radius) and show the localized server message.
//   INPUTS:  status: number — HTTP response status
//            detail?: string — server-provided detail (may be localized)
//   OUTPUTS: AddressApiError instance with .status, .detail, .name = 'AddressApiError'.
//   SIDE_EFFECTS: none.
//   LINKS:   AddressForm.renderError, CheckoutPage.renderError.
// END_CONTRACT: AddressApiError
// Ошибка CRUD-адресов: сохраняет HTTP-статус и detail для рендера 409 (радиус) в UI.
export class AddressApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'AddressApiError';
  }
}

function normalizeErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  return undefined;
}

async function parseError(res: Response): Promise<AddressApiError> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: unknown };
    detail = normalizeErrorDetail(body?.detail);
  } catch {
    // body не JSON — оставляем detail undefined
  }
  return new AddressApiError(res.status, detail);
}

// START_CONTRACT: listAddresses
//   PURPOSE: Fetch the current user's saved delivery addresses.
//   INPUTS:  none.
//   OUTPUTS: Promise<AddressResponse[]> — empty array if server returns non-array
//            (defensive fail-soft; the spec is bare JSON array).
//   SIDE_EFFECTS: HTTP GET /api/v1/profile/addresses (authenticated). Throws
//                 AddressApiError on non-2xx.
//   LINKS:   PDD §7 saved addresses; INV-013 PII handling.
// END_CONTRACT: listAddresses
export async function listAddresses(): Promise<AddressResponse[]> {
  const res = await authenticatedFetch('/api/v1/profile/addresses');
  if (!res.ok) throw await parseError(res);
  // Сервер возвращает bare JSON array. На любом не-array теле — fail-soft [].
  const data = (await res.json()) as unknown;
  return Array.isArray(data) ? (data as AddressResponse[]) : [];
}

// START_CONTRACT: createAddress
//   PURPOSE: Persist a new saved address for the current user.
//   INPUTS:  data: AddressCreatePayload — label + address_text + optional fields.
//   OUTPUTS: Promise<AddressResponse> — server-stored record with id and
//            is_default flag.
//   SIDE_EFFECTS: HTTP POST /api/v1/profile/addresses; throws AddressApiError
//                 on non-2xx (notably 409 out-of-radius).
//   LINKS:   PDD §7 add address; INV-013 (raw address text is PII).
// END_CONTRACT: createAddress
export async function createAddress(
  data: AddressCreatePayload,
): Promise<AddressResponse> {
  const res = await authenticatedFetch('/api/v1/profile/addresses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AddressResponse;
}

// START_CONTRACT: updateAddress
//   PURPOSE: Patch an existing address with partial fields.
//   INPUTS:  id: string — UUID of the address
//            data: AddressUpdatePayload — partial fields (incl. is_default flag)
//   OUTPUTS: Promise<AddressResponse> — updated record from the server.
//   SIDE_EFFECTS: HTTP PATCH /api/v1/profile/addresses/:id; throws
//                 AddressApiError on non-2xx (409 out-of-radius).
//   LINKS:   PDD §7 edit address; INV-013.
// END_CONTRACT: updateAddress
export async function updateAddress(
  id: string,
  data: AddressUpdatePayload,
): Promise<AddressResponse> {
  const res = await authenticatedFetch(`/api/v1/profile/addresses/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AddressResponse;
}

// START_CONTRACT: deleteAddress
//   PURPOSE: Remove an address by id.
//   INPUTS:  id: string — UUID of the address.
//   OUTPUTS: Promise<void>.
//   SIDE_EFFECTS: HTTP DELETE /api/v1/profile/addresses/:id; throws
//                 AddressApiError on non-2xx.
//   LINKS:   PDD §7 delete address.
// END_CONTRACT: deleteAddress
export async function deleteAddress(id: string): Promise<void> {
  const res = await authenticatedFetch(`/api/v1/profile/addresses/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw await parseError(res);
}

// START_CONTRACT: setDefaultAddress
//   PURPOSE: Mark an address as the user's default. Server has no dedicated
//            endpoint — we PATCH is_default=true and the backend handles the
//            implicit unset-other-defaults transaction (§5.2).
//   INPUTS:  id: string — UUID of the address to make default.
//   OUTPUTS: Promise<AddressResponse> — updated record.
//   SIDE_EFFECTS: HTTP PATCH /api/v1/profile/addresses/:id; throws on non-2xx.
//   LINKS:   docs/phase4_manual_test_scenarios.md §5.2.
// END_CONTRACT: setDefaultAddress
// Устанавливает адрес основным. Сервер не имеет dedicated endpoint — используем
// PATCH с флагом is_default=true (см. docs/phase4_manual_test_scenarios.md §5.2).
export async function setDefaultAddress(id: string): Promise<AddressResponse> {
  const res = await authenticatedFetch(`/api/v1/profile/addresses/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_default: true }),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AddressResponse;
}
