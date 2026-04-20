import { authenticatedFetch } from './client';

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

export type AddressUpdatePayload = Partial<AddressCreatePayload> & {
  is_default?: boolean;
};

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

async function parseError(res: Response): Promise<AddressApiError> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: string };
    detail = body?.detail;
  } catch {
    // body не JSON — оставляем detail undefined
  }
  return new AddressApiError(res.status, detail);
}

export async function listAddresses(): Promise<AddressResponse[]> {
  const res = await authenticatedFetch('/api/v1/profile/addresses');
  if (!res.ok) throw await parseError(res);
  // Сервер возвращает bare JSON array. На любом не-array теле — fail-soft [].
  const data = (await res.json()) as unknown;
  return Array.isArray(data) ? (data as AddressResponse[]) : [];
}

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

export async function deleteAddress(id: string): Promise<void> {
  const res = await authenticatedFetch(`/api/v1/profile/addresses/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw await parseError(res);
}

// Устанавливает адрес основным. Сервер не имеет dedicated endpoint — используем
// PATCH с флагом is_default=true (см. docs/phase4_manual_test_scenarios.md §5.2).
export async function setDefaultAddress(
  id: string,
): Promise<AddressResponse> {
  const res = await authenticatedFetch(`/api/v1/profile/addresses/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_default: true }),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AddressResponse;
}
