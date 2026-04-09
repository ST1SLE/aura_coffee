import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { AuthContext } from './AuthProvider';
import type { AuthContextValue } from './AuthProvider';

function renderWithAuth(authValue: AuthContextValue, initialRoute = '/protected') {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/protected" element={<div>Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

const baseAuth: AuthContextValue = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn(),
  verifyCode: vi.fn(),
  logout: vi.fn(),
};

describe('ProtectedRoute', () => {
  it('redirects unauthenticated user to /login', () => {
    renderWithAuth(baseAuth);
    expect(screen.getByText('Login Page')).toBeDefined();
  });

  it('renders content for authenticated user', () => {
    renderWithAuth({
      ...baseAuth,
      user: { id: 'u1', role: 'customer' },
      isAuthenticated: true,
    });
    expect(screen.getByText('Protected Content')).toBeDefined();
  });

  it('shows loading indicator while loading', () => {
    renderWithAuth({ ...baseAuth, isLoading: true });
    expect(screen.queryByText('Login Page')).toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });
});
