// Роль сотрудника. Источник истины — сервер (INV-010),
// localStorage хранит только UX-подсказку для роутинга.

import { useMemo } from 'react';

const STORAGE_KEY = 'staffRole';

export type StaffRole = 'admin' | 'barista' | 'courier';

const VALID_ROLES: readonly StaffRole[] = ['admin', 'barista', 'courier'];

export function getRole(): StaffRole | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === null) return null;
  return VALID_ROLES.includes(raw as StaffRole) ? (raw as StaffRole) : null;
}

export function setRole(role: StaffRole): void {
  localStorage.setItem(STORAGE_KEY, role);
}

export function clearRole(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// Роль не меняется в пределах сессии (login → logout через полный
// navigate), поэтому useMemo достаточно — подписка на storage events
// не нужна.
export function useCurrentRole(): StaffRole | null {
  return useMemo(() => getRole(), []);
}
