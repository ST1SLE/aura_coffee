import { authenticatedFetch } from './client';

export interface AddressResponse {
  id: string;
  text: string;
  lat: number | null;
  lon: number | null;
  label: string | null;
  apartment: string | null;
  entrance: string | null;
  floor: string | null;
  comment: string | null;
  is_primary: boolean;
}

export interface AddressCreatePayload {
  text: string;
  lat?: number | null;
  lon?: number | null;
  label?: string | null;
  apartment?: string | null;
  entrance?: string | null;
  floor?: string | null;
  comment?: string | null;
}

export type AddressUpdatePayload = Partial<AddressCreatePayload>;

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
  const body = (await res.json()) as { items?: AddressResponse[] };
  return body.items ?? [];
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

export async function setPrimaryAddress(
  id: string,
): Promise<AddressResponse> {
  const res = await authenticatedFetch(
    `/api/v1/profile/addresses/${id}/set-primary`,
    { method: 'POST' },
  );
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AddressResponse;
}
