import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './Layout';

const mockCartState = vi.hoisted(() => ({
  itemCount: 0,
  subtotal: 0,
  status: 'ready',
  refresh: vi.fn(),
}));
const mockAuthState = vi.hoisted(() => ({
  logout: vi.fn(),
  isAuthenticated: true,
  isLoading: false,
}));
const mockChangeLanguage = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: mockChangeLanguage },
  }),
}));

vi.mock('@/auth/useAuth', () => ({
  useAuth: () => mockAuthState,
}));

vi.mock('@/store/cart', () => ({
  useCartStore: (selector?: (state: typeof mockCartState) => unknown) =>
    selector ? selector(mockCartState) : mockCartState,
}));

function renderLayout(initialRoute = '/menu') {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/menu" element={<div>Menu route</div>} />
          <Route path="/menu/:categoryId" element={<div>Menu category</div>} />
          <Route path="/cart" element={<div>Cart route</div>} />
          <Route path="/orders" element={<div>Orders route</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockCartState.itemCount = 0;
  mockCartState.subtotal = 0;
  mockCartState.status = 'ready';
  mockAuthState.isAuthenticated = true;
  mockAuthState.isLoading = false;
  vi.clearAllMocks();
  mockCartState.refresh.mockResolvedValue(undefined);
});

describe('Layout cart affordances', () => {
  it('renders count-aware cart nav badges when cart has items', () => {
    mockCartState.itemCount = 3;
    const { container } = renderLayout('/orders');

    expect(screen.getAllByRole('link', { name: 'nav.cart: 3' }).length).toBe(2);
    expect(
      container.querySelectorAll('span[aria-hidden="true"]').length,
    ).toBeGreaterThan(0);
    expect(screen.queryByTestId('floating-cart-link')).toBeNull();
  });

  it('renders fixed floating cart link over menu when cart has items', () => {
    mockCartState.itemCount = 2;
    mockCartState.subtotal = 37500;
    renderLayout('/menu');

    const floating = screen.getByTestId('floating-cart-link');
    expect(floating.getAttribute('href')).toBe('/cart');
    expect(floating.getAttribute('aria-label')).toBe('nav.cart: 2');
    expect(floating.className).toContain('fixed');
    expect(floating.className).toContain('min-h-14');
    expect(floating.className).toContain('md:bottom-6');
    expect(floating.className).not.toContain('md:hidden');
    expect(screen.getByText(/375/)).toBeDefined();
  });

  it('hides cart badges and floating link when cart is empty', () => {
    renderLayout('/menu');

    expect(screen.getAllByRole('link', { name: 'nav.cart' }).length).toBe(2);
    expect(screen.queryByRole('link', { name: /nav\.cart: / })).toBeNull();
    expect(screen.queryByTestId('floating-cart-link')).toBeNull();
  });

  it('refreshes cart once when the shell mounts with idle cart state', () => {
    mockCartState.status = 'idle';
    renderLayout('/menu');

    expect(mockCartState.refresh).toHaveBeenCalledTimes(1);
  });

  it('does not refresh cart before auth state has resolved', () => {
    mockCartState.status = 'idle';
    mockAuthState.isLoading = true;
    renderLayout('/menu');

    expect(mockCartState.refresh).not.toHaveBeenCalled();
  });
});
