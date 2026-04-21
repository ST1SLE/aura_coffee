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

// Index-маршрут admin-only. Barista в admin+barista-layout'е редиректится
// на /orders, чтобы избежать loop'а внутреннего ProtectedRoute.
function DashboardIndex() {
  const role = useCurrentRole();
  if (role === 'admin') return <DashboardPage />;
  return <Navigate to="/orders" replace />;
}

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
        <Route path="settings" element={<SettingsPage />} />
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

export function App() {
  return (
    <BrowserRouter basename="/admin">
      <AppRoutes />
    </BrowserRouter>
  );
}
