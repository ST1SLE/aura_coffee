import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { getAccessToken } from '@/api/client';
import { getRole, type StaffRole } from '@/lib/auth';

// START_MODULE_CONTRACT
//   PURPOSE: Route guard component — redirects unauthenticated users to /login
//            with a returnUrl, and (when allowedRoles is given) redirects
//            wrong-role users to a sensible per-role default. UX gate only;
//            server is the source of truth.
//   SCOPE:   Wrapped around route subtrees in App.tsx (admin/barista layout,
//            admin-only inner routes, courier shell).
//   DEPENDS: react-router-dom (Navigate/useLocation), @/api/client (getAccessToken),
//            @/lib/auth (getRole).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN,
//            INV-002 (server enforces auth on every request — this guard is
//            purely UX/redirect), INV-010 (role isolation enforced server-side).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ProtectedRoute - guard that redirects on missing token or disallowed role
// END_MODULE_MAP

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: StaffRole[];
}

// START_CONTRACT: ProtectedRoute
//   PURPOSE: Gate a subtree on (a) presence of access token and (b) optional
//            role allow-list. Missing token → /login?returnUrl=<current>;
//            wrong role → /courier (couriers) or / (others). Pure UX redirect:
//            the API still rejects unauthorized requests at runtime.
//   INPUTS:  children: ReactNode, allowedRoles?: StaffRole[]
//   OUTPUTS: JSX.Element — children, or <Navigate replace .../>.
//   SIDE_EFFECTS: navigation via <Navigate>; reads localStorage via getRole/getAccessToken.
//   LINKS:   INV-002, INV-010 (server enforcement is the actual security boundary;
//            this component only steers UX so users do not see broken pages).
// END_CONTRACT: ProtectedRoute
export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const token = getAccessToken();
  const location = useLocation();

  if (!token) {
    const returnUrl = location.pathname + location.search;
    return (
      <Navigate
        to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`}
        replace
      />
    );
  }

  if (allowedRoles) {
    const role = getRole();
    if (role === null || !allowedRoles.includes(role)) {
      // UX-подсказка. Сервер — источник истины (INV-010).
      const target = role === 'courier' ? '/courier' : '/';
      return <Navigate to={target} replace />;
    }
  }

  return <>{children}</>;
}
