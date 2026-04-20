// Типы зеркалят Pydantic-схемы из services/core-api/core_api/schemas/courier.py
// (поставляется feat/delivery-assignment). При появлении OpenAPI-кодогенерации
// файл будет заменён целиком. Следует паттерну из menu.ts.

import { authenticatedFetch, ApiError } from './client';

export { ApiError };

export type CourierAssignmentStatus =
  | 'AWAITING_COURIER'
  | 'COURIER_ASSIGNED'
  | 'PICKED_UP'
  | 'DELIVERED'
  | 'CANCELLED';

export interface DeliveryAddressSnapshot {
  address_line: string;
  lat?: number | null;
  lon?: number | null;
  entrance?: string | null;
  apartment?: string | null;
  floor?: string | null;
  comment?: string | null;
}

export interface CourierAssignmentResponse {
  id: string;
  order_id: string;
  status: CourierAssignmentStatus;
  delivery_address: DeliveryAddressSnapshot;
  total: number;
  requested_time: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function post<T>(path: string): Promise<T> {
  return json<T>(path, { method: 'POST' });
}

export const listAvailable = (): Promise<CourierAssignmentResponse[]> =>
  json('/api/v1/courier/assignments/available');

export const takeAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/take`);

export const listMine = (): Promise<CourierAssignmentResponse[]> =>
  json('/api/v1/courier/assignments/mine');

export const pickupAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/pickup`);

export const deliverAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/deliver`);
