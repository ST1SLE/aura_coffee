import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './Layout';
import { setRole, clearRole, type StaffRole } from '@/lib/auth';

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

  it('barista sees only orders and menu', () => {
    renderLayout('barista');
    expect(screen.getByTestId('nav-orders')).toBeInTheDocument();
    expect(screen.getByTestId('nav-menu')).toBeInTheDocument();
    expect(screen.queryByTestId('nav-dashboard')).toBeNull();
    expect(screen.queryByTestId('nav-users')).toBeNull();
    expect(screen.queryByTestId('nav-promos')).toBeNull();
    expect(screen.queryByTestId('nav-settings')).toBeNull();
  });

  it('courier sees zero nav links', () => {
    renderLayout('courier');
    const links = screen.queryAllByTestId(/^nav-/);
    expect(links).toHaveLength(0);
  });

  it('null role renders zero nav links', () => {
    renderLayout(null);
    const links = screen.queryAllByTestId(/^nav-/);
    expect(links).toHaveLength(0);
  });
});
