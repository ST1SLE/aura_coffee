// Роль сотрудника. Источник истины — сервер (INV-010),
// localStorage хранит только UX-подсказку для роутинга.

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
