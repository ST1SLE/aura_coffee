import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LoginPage } from '@/pages/Login';
import { DashboardPage } from '@/pages/DashboardPage';
import { OrdersPage } from '@/pages/OrdersPage';
import { MenuPage } from '@/pages/Menu';
import { UsersPage } from '@/pages/UsersPage';
import { PromosPage } from '@/pages/Promos';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { CourierShell } from '@/pages/Courier/CourierShell';
import { CourierPage } from '@/pages/Courier/CourierPage';

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
        <Route index element={<DashboardPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="menu" element={<MenuPage />} />
        <Route path="users" element={<UsersPage />} />
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
