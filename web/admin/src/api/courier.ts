// Типы зеркалят Pydantic-схемы из services/core-api/core_api/schemas/courier.py
// (поставляется feat/delivery-assignment). При появлении OpenAPI-кодогенерации
// файл будет заменён целиком. Следует паттерну из menu.ts.

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for courier-only assignment endpoints — list available,
//            take, list mine, pickup, deliver.
//   SCOPE:   Wraps /api/v1/courier/assignments/*; mirrors core-api Pydantic
//            schemas in services/core-api/core_api/schemas/courier.py.
//   DEPENDS: ./client (authenticatedFetch, ApiError).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.5 delivery flow,
//            INV-002 (server enforces courier scope; admin may also call),
//            INV-010 (courier sees only delivery orders, no customer PII beyond address),
//            INV-016 (PICKED_UP / DELIVERED transitions are state-machine moves).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError                    - re-export from ./client
//   CourierAssignmentStatus     - assignment lifecycle union
//   DeliveryAddressSnapshot     - address shape (no name/phone — INV-010)
//   CourierAssignmentResponse   - assignment DTO returned by all courier endpoints
//   listAvailable               - GET available assignments (poll-driven feed)
//   takeAssignment              - POST take (claim) an available assignment
//   listMine                    - GET assignments I claimed
//   pickupAssignment            - POST mark picked up (INV-016 transition)
//   deliverAssignment           - POST mark delivered (INV-016 transition)
// END_MODULE_MAP

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

// START_CONTRACT: listAvailable
//   PURPOSE: List courier assignments awaiting pickup (status=AWAITING_COURIER).
//   INPUTS:  none
//   OUTPUTS: Promise<CourierAssignmentResponse[]>
//   SIDE_EFFECTS: GET; polled by AvailableTab every 5s.
//   LINKS:   INV-002, INV-010 (courier sees minimal PII).
// END_CONTRACT: listAvailable
export const listAvailable = (): Promise<CourierAssignmentResponse[]> =>
  json('/api/v1/courier/assignments/available');

// START_CONTRACT: takeAssignment
//   PURPOSE: Atomically claim an available assignment for the current courier.
//   INPUTS:  id: string — assignment UUID
//   OUTPUTS: Promise<CourierAssignmentResponse> — updated to COURIER_ASSIGNED.
//   SIDE_EFFECTS: POST; 409 if another courier already claimed it.
//   LINKS:   INV-002, INV-016.
// END_CONTRACT: takeAssignment
export const takeAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/take`);

// START_CONTRACT: listMine
//   PURPOSE: List assignments claimed by the current courier (active states).
//   INPUTS:  none
//   OUTPUTS: Promise<CourierAssignmentResponse[]>
//   SIDE_EFFECTS: GET; polled by MineTab every 5s.
//   LINKS:   INV-002, INV-010.
// END_CONTRACT: listMine
export const listMine = (): Promise<CourierAssignmentResponse[]> =>
  json('/api/v1/courier/assignments/mine');

// START_CONTRACT: pickupAssignment
//   PURPOSE: Mark an assignment as PICKED_UP (courier left the shop with the order).
//            This is an INV-016 state-machine transition; server validates source state.
//   INPUTS:  id: string
//   OUTPUTS: Promise<CourierAssignmentResponse>
//   SIDE_EFFECTS: POST; 409 on illegal source state.
//   LINKS:   INV-002, INV-016.
// END_CONTRACT: pickupAssignment
export const pickupAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/pickup`);

// START_CONTRACT: deliverAssignment
//   PURPOSE: Mark an assignment as DELIVERED (terminal success state).
//            INV-016 state-machine transition.
//   INPUTS:  id: string
//   OUTPUTS: Promise<CourierAssignmentResponse>
//   SIDE_EFFECTS: POST; 409 on illegal source state.
//   LINKS:   INV-002, INV-016.
// END_CONTRACT: deliverAssignment
export const deliverAssignment = (
  id: string,
): Promise<CourierAssignmentResponse> =>
  post(`/api/v1/courier/assignments/${id}/deliver`);
