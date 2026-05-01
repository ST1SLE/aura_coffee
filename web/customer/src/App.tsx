import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/auth/AuthProvider';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { Layout } from '@/components/Layout';
import { LoginPage } from '@/pages/LoginPage';
import { VerifyPage } from '@/pages/VerifyPage';
import { CartPage } from '@/pages/Cart/CartPage';
import { MenuPage } from '@/pages/Menu/MenuPage';
import { CheckoutPage } from '@/pages/CheckoutPage';
import { OrdersPage } from '@/pages/OrdersPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { AddressesPage } from '@/pages/Profile/Addresses/AddressesPage';
import { LoyaltyPage } from '@/pages/Profile/Loyalty/LoyaltyPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

// START_MODULE_CONTRACT
//   PURPOSE: Top-level App component — wires BrowserRouter + AuthProvider and
//            declares the customer SPA route tree (public LoginPage/VerifyPage,
//            then ProtectedRoute-gated pages under the shared Layout).
//   SCOPE:   App component (only export).
//   DEPENDS: react-router-dom, AuthProvider, ProtectedRoute, Layout, all page
//            components.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4 boundaries.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   App  - root SPA component: BrowserRouter -> AuthProvider -> Routes
// END_MODULE_MAP

// START_CONTRACT: App
//   PURPOSE: Mount the SPA's router and auth provider, declare the route tree.
//            The authenticated index redirects to /menu so the app opens on
//            the real ordering surface.
//   INPUTS:  none.
//   OUTPUTS: JSX — entire route tree rendered through react-router.
//   SIDE_EFFECTS: registers BrowserRouter (history), creates AuthContext.
//                 Routes under <ProtectedRoute> redirect to /login when
//                 unauthenticated (INV-002 — UX guard, server enforces).
//   LINKS:   PDD §4.4; ProtectedRoute and Layout are the layout routes.
// END_CONTRACT: App
export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<LoginPage />} />
          <Route path="login/verify" element={<VerifyPage />} />
          <Route element={<Layout />}>
            <Route element={<ProtectedRoute />}>
              <Route index element={<Navigate to="/menu" replace />} />
              <Route path="menu" element={<MenuPage />} />
              <Route path="menu/:categoryId" element={<MenuPage />} />
              <Route path="cart" element={<CartPage />} />
              <Route path="checkout" element={<CheckoutPage />} />
              <Route path="orders" element={<OrdersPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="profile/addresses" element={<AddressesPage />} />
              <Route path="profile/loyalty" element={<LoyaltyPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
