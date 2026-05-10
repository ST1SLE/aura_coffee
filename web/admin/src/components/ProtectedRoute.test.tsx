import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { clearAuthTokens, getAccessToken, setAccessToken } from '@/api/client';
import type { StaffRole } from '@/lib/auth';

interface SetupOpts {
  path: string;
  token: string | null;
  role?: StaffRole | null;
  allowedRoles?: StaffRole[];
}

function renderWithRouter({ path, token, role, allowedRoles }: SetupOpts) {
  clearAuthTokens();
  if (token) {
    setAccessToken(token);
  }
  if (role) {
    localStorage.setItem('staffRole', role);
  } else {
    localStorage.removeItem('staffRole');
  }

  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>login-page</div>} />
        <Route path="/" element={<div>dashboard</div>} />
        <Route path="/courier" element={<div>courier-page</div>} />
        <Route
          path="/menu"
          element={
            <ProtectedRoute allowedRoles={allowedRoles}>
              <div>protected-content</div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/courier-gated"
          element={
            <ProtectedRoute allowedRoles={allowedRoles}>
              <div>courier-gated-content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear();
    clearAuthTokens();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{}', { status: 401 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('с токеном: рендерит дочерний элемент (без allowedRoles — legacy)', () => {
    renderWithRouter({ path: '/menu', token: 'valid-token' });
    expect(screen.getByText('protected-content')).toBeDefined();
  });

  it('без токена: рендерит страницу логина', async () => {
    renderWithRouter({ path: '/menu', token: null });
    await waitFor(() => {
      expect(screen.getByText('login-page')).toBeDefined();
    });
  });

  it('без токена даже с allowedRoles: редирект на логин', async () => {
    renderWithRouter({
      path: '/menu',
      token: null,
      allowedRoles: ['admin'],
    });
    await waitFor(() => {
      expect(screen.getByText('login-page')).toBeDefined();
    });
  });

  it('replace: страница защищена', async () => {
    const { container } = renderWithRouter({ path: '/menu', token: null });
    await waitFor(() => {
      expect(container.textContent).toContain('login-page');
    });
  });

  it('без in-memory token: восстанавливает сессию через refresh cookie', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'access-new',
          refresh_token: 'refresh-new',
          role: 'admin',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    renderWithRouter({
      path: '/menu',
      token: null,
      allowedRoles: ['admin'],
    });

    await waitFor(() => {
      expect(screen.getByText('protected-content')).toBeDefined();
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/staff/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    expect(getAccessToken()).toBe('access-new');
    expect(localStorage.getItem('accessToken')).toBeNull();
  });

  it('courier на admin-роуте: редирект на /courier', () => {
    renderWithRouter({
      path: '/menu',
      token: 'tok',
      role: 'courier',
      allowedRoles: ['admin', 'barista'],
    });
    expect(screen.getByText('courier-page')).toBeDefined();
    expect(screen.queryByText('protected-content')).toBeNull();
  });

  it('barista на courier-роуте: редирект на /', () => {
    renderWithRouter({
      path: '/courier-gated',
      token: 'tok',
      role: 'barista',
      allowedRoles: ['admin', 'courier'],
    });
    expect(screen.getByText('dashboard')).toBeDefined();
    expect(screen.queryByText('courier-gated-content')).toBeNull();
  });

  it('admin допущен на admin-роут', () => {
    renderWithRouter({
      path: '/menu',
      token: 'tok',
      role: 'admin',
      allowedRoles: ['admin', 'barista'],
    });
    expect(screen.getByText('protected-content')).toBeDefined();
  });

  it('admin допущен на courier-роут', () => {
    renderWithRouter({
      path: '/courier-gated',
      token: 'tok',
      role: 'admin',
      allowedRoles: ['admin', 'courier'],
    });
    expect(screen.getByText('courier-gated-content')).toBeDefined();
  });

  it('null роль с allowedRoles: редирект на /', () => {
    renderWithRouter({
      path: '/menu',
      token: 'tok',
      role: null,
      allowedRoles: ['admin'],
    });
    expect(screen.getByText('dashboard')).toBeDefined();
  });

  it('courier на courier-роуте: рендерится', () => {
    renderWithRouter({
      path: '/courier-gated',
      token: 'tok',
      role: 'courier',
      allowedRoles: ['admin', 'courier'],
    });
    expect(screen.getByText('courier-gated-content')).toBeDefined();
  });

  // INV-010: barista видит все admin+barista маршруты, но /settings закрыт
  // inner ProtectedRoute allowedRoles={['admin']} → редирект на /.
  it('barista на /settings с inner admin-guard: редирект на /', () => {
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'barista');

    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route path="/" element={<div>dashboard</div>} />
          <Route
            path="/settings"
            element={
              <ProtectedRoute allowedRoles={['admin', 'barista']}>
                <ProtectedRoute allowedRoles={['admin']}>
                  <div>settings-page</div>
                </ProtectedRoute>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('dashboard')).toBeDefined();
    expect(screen.queryByText('settings-page')).toBeNull();
  });

  it('admin на /settings с inner admin-guard: рендерится', () => {
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'admin');

    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route path="/" element={<div>dashboard</div>} />
          <Route
            path="/settings"
            element={
              <ProtectedRoute allowedRoles={['admin', 'barista']}>
                <ProtectedRoute allowedRoles={['admin']}>
                  <div>settings-page</div>
                </ProtectedRoute>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('settings-page')).toBeDefined();
  });
});
