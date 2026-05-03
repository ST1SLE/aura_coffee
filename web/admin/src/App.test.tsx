import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@/i18n/config';
import { App, AppRoutes } from '@/App';
import * as statsApi from '@/api/admin-stats';

vi.mock('@/api/admin-stats', async () => {
  const actual = await vi.importActual<typeof import('@/api/admin-stats')>('@/api/admin-stats');
  return {
    ...actual,
    getAdminStats: vi.fn().mockResolvedValue({
      range: 'month',
      range_start: '2026-03-21T00:00:00Z',
      range_end: '2026-04-20T00:00:00Z',
      revenue_kopecks: 0,
      orders_count: 0,
      popular_items: [],
    }),
  };
});

// Дымовые тесты App — полноценное роутинговое поведение покрывается
// ProtectedRoute.test.tsx и LoginPage.test.tsx через MemoryRouter.
// BrowserRouter с basename="/admin" в jsdom не выполняет полноценную навигацию.

function renderAt(path: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  function renderBrowserApp(path = '/admin') {
    window.history.pushState({}, '', path);
    return render(<App />);
  }

  it('рендерится без краша (без токена)', () => {
    const { container } = renderBrowserApp();
    expect(container).toBeDefined();
  });

  it('рендерится без краша (с токеном в localStorage)', () => {
    localStorage.setItem('accessToken', 'valid-token');
    const { container } = renderBrowserApp();
    expect(container).toBeDefined();
  });

  it('/courier с ролью courier рендерит курьерский shell (без sidebar)', async () => {
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'courier');

    renderAt('/courier');

    // Курьерский shell не содержит навигации с ссылкой на "Меню" из Layout
    await waitFor(() => {
      const nav = document.querySelector('aside');
      expect(nav).toBeNull();
    });
    // Табы курьера должны быть отрендерены
    expect(screen.getAllByRole('tab').length).toBeGreaterThan(0);
  });

  it('/courier с ролью admin не рендерит courier shell', async () => {
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'admin');

    renderAt('/courier');

    await waitFor(() => {
      expect(
        screen.queryByRole('tab', { name: /доступные|available/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('tab', { name: /мои|mine/i }),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  it('/menu с ролью courier редиректит на /courier', async () => {
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'courier');

    renderAt('/menu');

    await waitFor(() => {
      expect(screen.getAllByRole('tab').length).toBeGreaterThan(0);
    });
  });

  it('/ с ролью admin рендерит DashboardPage', async () => {
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'admin');

    renderAt('/');

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
    expect(statsApi.getAdminStats).toHaveBeenCalled();
  });

  it('/ с ролью barista редиректит на /orders (dashboard не монтируется)', async () => {
    vi.mocked(statsApi.getAdminStats).mockClear();
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'barista');

    renderAt('/');

    // OrdersPage — stub с тайтлом "Заказы" / "Orders"; dashboard не монтируется.
    await waitFor(() => {
      expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
    });
    expect(statsApi.getAdminStats).not.toHaveBeenCalled();
  });
});
