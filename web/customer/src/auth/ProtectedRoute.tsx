import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './useAuth';

// START_MODULE_CONTRACT
//   PURPOSE: react-router route-level guard — renders <Outlet/> only when the
//            user is authenticated. Otherwise redirects to /login carrying the
//            current path as returnUrl in location.state. INV-002: this is a
//            UX guard only; the server enforces auth on every API call.
//   SCOPE:   ProtectedRoute component.
//   DEPENDS: react-router-dom, ./useAuth.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6; App.tsx wraps
//            authenticated routes with this layout route.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ProtectedRoute  - route layout component: spinner -> Navigate(/login) | Outlet
// END_MODULE_MAP

// START_CONTRACT: ProtectedRoute
//   PURPOSE: Block child routes until auth state has been resolved; redirect
//            to /login when not authenticated.
//   INPUTS:  none (reads useAuth + useLocation).
//   OUTPUTS: JSX — spinner while isLoading, <Navigate> to /login otherwise,
//            <Outlet/> when authenticated.
//   SIDE_EFFECTS: navigation via <Navigate replace>; passes returnUrl through
//                 location.state. INV-002 — the server still validates every
//                 request; this only controls UX.
//   LINKS:   App.tsx route tree; LoginPage reads location.state.returnUrl.
// END_CONTRACT: ProtectedRoute
export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ returnUrl: location.pathname }} replace />;
  }

  return <Outlet />;
}
