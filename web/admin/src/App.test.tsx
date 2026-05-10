import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@/i18n/config';
import { App, AppRoutes } from '@/App';
import { clearAuthTokens, setAccessToken } from '@/api/client';
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
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    clearAuthTokens();
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes('/api/v1/admin/orders')
        ? { orders: [], total_count: 0, page: 1, per_page: 20 }
        : url.includes('/api/v1/courier/assignments')
          ? []
          : {};

      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function renderBrowserApp(path = '/admin') {
    window.history.pushState({}, '', path);
    return render(<App />);
  }

  it('рендерится без краша (без токена)', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 401 }));
    const { container } = renderBrowserApp();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/staff/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({}),
      });
    });
    expect(container).toBeDefined();
  });

  it('рендерится без краша (с in-memory токеном)', () => {
    setAccessToken('valid-token');
    const { container } = renderBrowserApp();
    expect(container).toBeDefined();
  });

  it('/courier с ролью courier рендерит курьерский shell (без sidebar)', async () => {
    setAccessToken('tok');
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
    setAccessToken('tok');
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
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'courier');

    renderAt('/menu');

    await waitFor(() => {
      expect(screen.getAllByRole('tab').length).toBeGreaterThan(0);
    });
  });

  it('/ с ролью admin рендерит DashboardPage', async () => {
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'admin');

    renderAt('/');

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
    expect(statsApi.getAdminStats).toHaveBeenCalled();
  });

  it('/ с ролью barista редиректит на /orders (dashboard не монтируется)', async () => {
    vi.mocked(statsApi.getAdminStats).mockClear();
    setAccessToken('tok');
    localStorage.setItem('staffRole', 'barista');

    renderAt('/');

    // OrdersPage — stub с тайтлом "Заказы" / "Orders"; dashboard не монтируется.
    await waitFor(() => {
      expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
    });
    expect(statsApi.getAdminStats).not.toHaveBeenCalled();
  });
});
