import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@/i18n/config';
import { App, AppRoutes } from '@/App';

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

  it('рендерится без краша (без токена)', () => {
    const { container } = render(<App />);
    expect(container).toBeDefined();
  });

  it('рендерится без краша (с токеном в localStorage)', () => {
    localStorage.setItem('accessToken', 'valid-token');
    const { container } = render(<App />);
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

  it('/menu с ролью courier редиректит на /courier', async () => {
    localStorage.setItem('accessToken', 'tok');
    localStorage.setItem('staffRole', 'courier');

    renderAt('/menu');

    await waitFor(() => {
      expect(screen.getAllByRole('tab').length).toBeGreaterThan(0);
    });
  });
});
