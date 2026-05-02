import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './Layout';

const mockCartState = vi.hoisted(() => ({ itemCount: 0 }));
const mockLogout = vi.hoisted(() => vi.fn());
const mockChangeLanguage = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: mockChangeLanguage },
  }),
}));

vi.mock('@/auth/useAuth', () => ({
  useAuth: () => ({ logout: mockLogout }),
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
  vi.clearAllMocks();
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
    renderLayout('/menu');

    const floating = screen.getByTestId('floating-cart-link');
    expect(floating.getAttribute('href')).toBe('/cart');
    expect(floating.getAttribute('aria-label')).toBe('nav.cart: 2');
    expect(floating.className).toContain('fixed');
    expect(floating.className).toContain('min-h-11');
  });

  it('hides cart badges and floating link when cart is empty', () => {
    renderLayout('/menu');

    expect(screen.getAllByRole('link', { name: 'nav.cart' }).length).toBe(2);
    expect(screen.queryByRole('link', { name: /nav\.cart: / })).toBeNull();
    expect(screen.queryByTestId('floating-cart-link')).toBeNull();
  });
});
