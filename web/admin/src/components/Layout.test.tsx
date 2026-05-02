import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import '@/i18n/config';
import { Layout } from './Layout';
import { logout } from '@/api/client';
import { setRole, clearRole, type StaffRole } from '@/lib/auth';

vi.mock('@/api/client', () => ({
  logout: vi.fn(),
}));

function renderLayout(role: StaffRole | null) {
  if (role) {
    setRole(role);
  } else {
    clearRole();
  }

  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<div>home</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('Layout role-filtered sidebar', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(logout).mockClear();
  });

  it('admin sees all 6 nav items', () => {
    renderLayout('admin');
    expect(screen.getByTestId('nav-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('nav-orders')).toBeInTheDocument();
    expect(screen.getByTestId('nav-menu')).toBeInTheDocument();
    expect(screen.getByTestId('nav-users')).toBeInTheDocument();
    expect(screen.getByTestId('nav-promos')).toBeInTheDocument();
    expect(screen.getByTestId('nav-settings')).toBeInTheDocument();
  });

  it('admin mobile nav reuses all 6 role-filtered items', () => {
    renderLayout('admin');
    expect(screen.getByTestId('mobile-nav')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-orders')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-menu')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-users')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-promos')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-settings')).toBeInTheDocument();
  });

  it('barista sees only orders and menu', () => {
    renderLayout('barista');
    expect(screen.getByTestId('nav-orders')).toBeInTheDocument();
    expect(screen.getByTestId('nav-menu')).toBeInTheDocument();
    expect(screen.queryByTestId('nav-dashboard')).toBeNull();
    expect(screen.queryByTestId('nav-users')).toBeNull();
    expect(screen.queryByTestId('nav-promos')).toBeNull();
    expect(screen.queryByTestId('nav-settings')).toBeNull();
  });

  it('barista mobile nav includes only orders and menu', () => {
    renderLayout('barista');
    expect(screen.getByTestId('nav-mobile-orders')).toBeInTheDocument();
    expect(screen.getByTestId('nav-mobile-menu')).toBeInTheDocument();
    expect(screen.queryByTestId('nav-mobile-dashboard')).toBeNull();
    expect(screen.queryByTestId('nav-mobile-users')).toBeNull();
    expect(screen.queryByTestId('nav-mobile-promos')).toBeNull();
    expect(screen.queryByTestId('nav-mobile-settings')).toBeNull();
  });

  it('courier sees zero nav links', () => {
    renderLayout('courier');
    const links = screen.queryAllByTestId(/^nav-/);
    expect(links).toHaveLength(0);
    expect(screen.queryByTestId('mobile-nav')).toBeNull();
  });

  it('null role renders zero nav links', () => {
    renderLayout(null);
    const links = screen.queryAllByTestId(/^nav-/);
    expect(links).toHaveLength(0);
    expect(screen.queryByTestId('mobile-nav')).toBeNull();
  });

  it('renders logout action and delegates to api client logout', () => {
    renderLayout('admin');

    fireEvent.click(screen.getByTestId('logout-sidebar'));

    expect(logout).toHaveBeenCalledTimes(1);
  });
});
