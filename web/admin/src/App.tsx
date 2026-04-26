import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LoginPage } from '@/pages/Login';
import { DashboardPage } from '@/pages/DashboardPage';
import { OrdersPage } from '@/pages/Orders';
import { MenuPage } from '@/pages/Menu';
import { UsersPage } from '@/pages/Users';
import { PromosPage } from '@/pages/Promos';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { CourierShell } from '@/pages/Courier/CourierShell';
import { CourierPage } from '@/pages/Courier/CourierPage';
import { useCurrentRole } from '@/lib/auth';

// START_MODULE_CONTRACT
//   PURPOSE: Top-level route configuration for the staff SPA — defines the
//            login route, the admin/barista layout subtree (with admin-only
//            inner gates for users/promos/settings), and the courier shell
//            subtree. Mounted under basename="/admin".
//   SCOPE:   Everything routing-related lives here. Uses ProtectedRoute for
//            client-side role gating; server enforces actual access.
//   DEPENDS: react-router-dom, all page components, ProtectedRoute, Layout,
//            CourierShell, useCurrentRole.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (role isolation),
//            INV-002 (server is source of truth for auth/role),
//            INV-010 (admin-only routes for users/promos/settings).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AppRoutes - <Routes> tree with login + admin/barista layout + courier shell
//   App       - <BrowserRouter basename="/admin"> wrapper around AppRoutes
// END_MODULE_MAP

// Index-маршрут admin-only. Barista в admin+barista-layout'е редиректится
// на /orders, чтобы избежать loop'а внутреннего ProtectedRoute.
function DashboardIndex() {
  const role = useCurrentRole();
  if (role === 'admin') return <DashboardPage />;
  return <Navigate to="/orders" replace />;
}

// START_CONTRACT: AppRoutes
//   PURPOSE: Render the staff SPA route tree. /login is unauthenticated; the
//            admin+barista layout subtree wraps a default DashboardIndex and
//            inner admin-only gates; /courier is its own shell.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element (Routes).
//   SIDE_EFFECTS: navigation only (declarative routing).
//   LINKS:   INV-002, INV-010 (server enforces — these route gates are UX only,
//            they ensure the user sees the right surface and their deep links
//            resolve to a sensible default if their role doesn't match).
// END_CONTRACT: AppRoutes
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute allowedRoles={['admin', 'barista']}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardIndex />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="menu" element={<MenuPage />} />
        <Route
          path="users"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="promos"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <PromosPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="settings"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
      </Route>
      <Route
        element={
          <ProtectedRoute allowedRoles={['admin', 'courier']}>
            <CourierShell />
          </ProtectedRoute>
        }
      >
        <Route path="courier" element={<CourierPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

// START_CONTRACT: App
//   PURPOSE: Wrap AppRoutes in <BrowserRouter basename="/admin"> — single entry
//            point used by main.tsx.
//   INPUTS:  none.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: BrowserRouter installs a popstate listener.
// END_CONTRACT: App
export function App() {
  return (
    <BrowserRouter basename="/admin">
      <AppRoutes />
    </BrowserRouter>
  );
}
