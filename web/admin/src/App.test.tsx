import { render } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import '@/i18n/config';
import { App } from '@/App';

// Дымовые тесты App — полноценное роутинговое поведение покрывается
// ProtectedRoute.test.tsx и LoginPage.test.tsx через MemoryRouter.
// BrowserRouter с basename="/admin" в jsdom не выполняет полноценную навигацию.

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
});
