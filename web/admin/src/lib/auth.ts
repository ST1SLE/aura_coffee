// Роль сотрудника. Источник истины — сервер (INV-010),
// localStorage хранит только UX-подсказку для роутинга.

import { useMemo } from 'react';

// START_MODULE_CONTRACT
//   PURPOSE: Client-side staff role hint stored in localStorage. Used purely for
//            UX routing and conditional rendering — server is source of truth
//            (INV-002 / INV-010). Includes a useCurrentRole hook for components.
//   SCOPE:   Set by LoginPage after successful staffLogin; cleared by client.logout.
//   DEPENDS: react (useMemo), localStorage.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §4.5,
//            INV-002 (auth/role server-enforced), INV-010 (role isolation).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   StaffRole       - 'admin' | 'barista' | 'courier'
//   getRole         - read role hint from localStorage (validated against union)
//   setRole         - persist role hint after login
//   clearRole       - remove role hint on logout
//   useCurrentRole  - React hook returning the role hint stable per session
// END_MODULE_MAP

const STORAGE_KEY = 'staffRole';

export type StaffRole = 'admin' | 'barista' | 'courier';

const VALID_ROLES: readonly StaffRole[] = ['admin', 'barista', 'courier'];

// START_CONTRACT: getRole
//   PURPOSE: Read the persisted staff role hint, defensively validating against
//            the StaffRole union so a tampered/stale localStorage value yields null.
//   INPUTS:  none
//   OUTPUTS: StaffRole | null
//   SIDE_EFFECTS: reads localStorage.
//   LINKS:   INV-002 (this is a UX hint only; server is source of truth).
// END_CONTRACT: getRole
export function getRole(): StaffRole | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === null) return null;
  return VALID_ROLES.includes(raw as StaffRole) ? (raw as StaffRole) : null;
}

// START_CONTRACT: setRole
//   PURPOSE: Persist the role hint after successful login.
//   INPUTS:  role: StaffRole
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
//   LINKS:   INV-002.
// END_CONTRACT: setRole
export function setRole(role: StaffRole): void {
  localStorage.setItem(STORAGE_KEY, role);
}

// START_CONTRACT: clearRole
//   PURPOSE: Remove the role hint (logout / 401 cleanup).
//   INPUTS:  none
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
//   LINKS:   INV-002.
// END_CONTRACT: clearRole
export function clearRole(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// START_CONTRACT: useCurrentRole
//   PURPOSE: React hook returning the current role hint memoized once per mount;
//            role is immutable for the lifetime of an authenticated session
//            (login → logout always goes through a full window.location.assign),
//            so subscribing to storage events is unnecessary.
//   INPUTS:  none
//   OUTPUTS: StaffRole | null
//   SIDE_EFFECTS: none (memoized read).
//   LINKS:   INV-002 (server enforces role on every request — this hook only
//            decides what UI to render and where to redirect).
// END_CONTRACT: useCurrentRole
export function useCurrentRole(): StaffRole | null {
  return useMemo(() => getRole(), []);
}
