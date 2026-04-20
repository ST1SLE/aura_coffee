import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import type { StaffRole } from '@/lib/auth';

interface SetupOpts {
  path: string;
  token: string | null;
  role?: StaffRole | null;
  allowedRoles?: StaffRole[];
}

function renderWithRouter({ path, token, role, allowedRoles }: SetupOpts) {
  if (token) {
    localStorage.setItem('accessToken', token);
  } else {
    localStorage.removeItem('accessToken');
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
  });

  it('с токеном: рендерит дочерний элемент (без allowedRoles — legacy)', () => {
    renderWithRouter({ path: '/menu', token: 'valid-token' });
    expect(screen.getByText('protected-content')).toBeDefined();
  });

  it('без токена: рендерит страницу логина', () => {
    renderWithRouter({ path: '/menu', token: null });
    expect(screen.getByText('login-page')).toBeDefined();
  });

  it('без токена даже с allowedRoles: редирект на логин', () => {
    renderWithRouter({
      path: '/menu',
      token: null,
      allowedRoles: ['admin'],
    });
    expect(screen.getByText('login-page')).toBeDefined();
  });

  it('replace: страница защищена', () => {
    const { container } = renderWithRouter({ path: '/menu', token: null });
    expect(container.textContent).toContain('login-page');
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
});
