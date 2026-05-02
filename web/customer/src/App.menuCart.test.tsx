import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru', on: vi.fn(), off: vi.fn() },
  }),
}));
vi.mock('@/api/auth', () => ({
  sendCode: vi.fn(),
  verifyCode: vi.fn(),
  refreshTokens: vi.fn(),
  logout: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  registerAuthFailureHandler: vi.fn(),
  authenticatedFetch: vi.fn(),
  apiRequest: vi.fn(),
}));
vi.mock('@/api/menu', () => ({
  fetchPublicMenu: vi.fn().mockResolvedValue({ categories: [] }),
}));
vi.mock('@/store/cart', () => ({
  useCartStore: vi.fn(() => ({
    status: 'ready',
    items: [],
    subtotal: 0,
    currency: 'RUB',
    expiresAt: null,
    itemCount: 0,
    refresh: vi.fn().mockResolvedValue(undefined),
    addItem: vi.fn(),
    updateQuantity: vi.fn(),
    removeItem: vi.fn(),
  })),
}));

import { AuthContext } from '@/auth/AuthProvider';
import type { AuthContextValue } from '@/auth/AuthProvider';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { LoginPage } from '@/pages/LoginPage';
import { MenuPage } from '@/pages/Menu/MenuPage';
import { CartPage } from '@/pages/Cart/CartPage';

const unauthValue: AuthContextValue = {
  user: null, isAuthenticated: false, isLoading: false,
  login: vi.fn(), verifyCode: vi.fn(), logout: vi.fn(),
};
const authValue: AuthContextValue = {
  ...unauthValue,
  user: { id: 'u1', role: 'customer' },
  isAuthenticated: true,
};

function AppRoutes({ initialRoute = '/' }: { initialRoute?: string }) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/menu" element={<MenuPage />} />
          <Route path="/cart" element={<CartPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('App routing — menu and cart (task 8.2)', () => {
  it('unauthenticated /menu redirects to /login', () => {
    render(
      <AuthContext.Provider value={unauthValue}>
        <AppRoutes initialRoute="/menu" />
      </AuthContext.Provider>,
    );
    // LoginPage renders a phone input
    expect(screen.getByRole('textbox')).toBeDefined();
  });

  it('unauthenticated /cart redirects to /login', () => {
    render(
      <AuthContext.Provider value={unauthValue}>
        <AppRoutes initialRoute="/cart" />
      </AuthContext.Provider>,
    );
    expect(screen.getByRole('textbox')).toBeDefined();
  });

  it('authenticated /menu renders MenuPage', async () => {
    render(
      <AuthContext.Provider value={authValue}>
        <AppRoutes initialRoute="/menu" />
      </AuthContext.Provider>,
    );
    await screen.findByText('menu.empty');
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('authenticated /cart renders CartPage', () => {
    render(
      <AuthContext.Provider value={authValue}>
        <AppRoutes initialRoute="/cart" />
      </AuthContext.Provider>,
    );
    expect(screen.queryByRole('textbox')).toBeNull();
    // CartPage показывает skeleton или empty state — не LoginPage
  });
});
