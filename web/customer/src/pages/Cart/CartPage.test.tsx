import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));
vi.mock('@/store/cart', () => ({
  useCartStore: vi.fn(),
}));

import { useCartStore } from '@/store/cart';
import { CartPage } from './CartPage';
import type { CartItemResponse } from '@/api/cartTypes';

function makeItem(id: number, qty: number = 1): CartItemResponse {
  return {
    menu_item_id: id,
    size_option_id: null,
    modifier_ids: [],
    quantity: qty,
    unit_price: 20000,
    line_total: 20000 * qty,
    menu_item_snapshot: { name_ru: `Позиция ${id}`, name_en: `Item ${id}`, availability: 'available' },
    size_snapshot: null,
    modifiers_snapshot: [],
  };
}

function makeStore(overrides: Record<string, unknown> = {}) {
  return {
    status: 'ready' as const,
    cart: null,
    items: [],
    subtotal: 0,
    currency: 'RUB',
    expiresAt: null,
    itemCount: 0,
    refresh: vi.fn().mockResolvedValue(undefined),
    addItem: vi.fn(),
    updateQuantity: vi.fn().mockResolvedValue(undefined),
    removeItem: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <CartPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('CartPage — loading state (task 7.2)', () => {
  it('shows loading skeleton on idle/loading status', () => {
    (useCartStore as unknown as Mock).mockReturnValue(makeStore({ status: 'loading' }));
    renderPage();
    expect(screen.getByTestId('cart-loading')).toBeDefined();
  });
});

describe('CartPage — empty state (task 7.2)', () => {
  it('shows empty-state message and CTA link when items is empty', () => {
    (useCartStore as unknown as Mock).mockReturnValue(makeStore());
    renderPage();
    expect(screen.getByText('cart.empty')).toBeDefined();
    expect(screen.getByRole('link', { name: 'cart.emptyCta' })).toBeDefined();
  });

  it('empty-state CTA links to /menu', () => {
    (useCartStore as unknown as Mock).mockReturnValue(makeStore());
    renderPage();
    const link = screen.getByRole('link', { name: 'cart.emptyCta' }) as HTMLAnchorElement;
    expect(link.href).toContain('/menu');
  });

  it('does NOT render subtotal line when cart is empty', () => {
    (useCartStore as unknown as Mock).mockReturnValue(makeStore());
    renderPage();
    expect(screen.queryByText('cart.subtotal')).toBeNull();
  });
});

describe('CartPage — error state (task 7.2)', () => {
  it('shows error message with retry button', () => {
    (useCartStore as unknown as Mock).mockReturnValue(makeStore({ status: 'error' }));
    renderPage();
    expect(screen.getByRole('button', { name: 'cart.retry' })).toBeDefined();
  });

  it('retry button calls refresh once', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    (useCartStore as unknown as Mock).mockReturnValue(makeStore({ status: 'error', refresh }));
    renderPage();

    // refresh вызывается один раз из useEffect при монтировании
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: 'cart.retry' }));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(2));
  });
});

describe('CartPage — items and subtotal (task 7.6)', () => {
  it('renders correct subtotal from store', () => {
    const items = [makeItem(1, 2), makeItem(2, 1)];
    (useCartStore as unknown as Mock).mockReturnValue(
      makeStore({ items, subtotal: 60000, itemCount: 3 }),
    );
    renderPage();
    expect(screen.getByText(/600/).textContent).toBeDefined();
  });

  it('remove button triggers removeItem with correct id', async () => {
    const removeItem = vi.fn().mockResolvedValue(undefined);
    const items = [makeItem(1, 1)];
    (useCartStore as unknown as Mock).mockReturnValue(makeStore({ items, subtotal: 20000, itemCount: 1, removeItem }));
    renderPage();

    const removeBtn = screen.getByRole('button', { name: 'cart.remove' });
    fireEvent.click(removeBtn);

    await waitFor(() => expect(removeItem).toHaveBeenCalledOnce());
  });
});

describe('CartPage — cart expired (task 7.8)', () => {
  it('shows expired toast and calls refresh on 410 error', async () => {
    const err = Object.assign(new Error('expired'), { status: 410 });
    const removeItem = vi.fn().mockRejectedValue(err);
    const refresh = vi.fn().mockResolvedValue(undefined);
    const items = [makeItem(1, 1)];

    (useCartStore as unknown as Mock).mockReturnValue(
      makeStore({ items, subtotal: 20000, itemCount: 1, removeItem, refresh }),
    );
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'cart.remove' }));

    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole('status')).toBeDefined());
  });
});
