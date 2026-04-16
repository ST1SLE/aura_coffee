// Хранилище корзины: zustand
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('@/api/cart', () => ({
  getCart: vi.fn(),
  addItem: vi.fn(),
  updateItem: vi.fn(),
  removeItem: vi.fn(),
  clearCart: vi.fn(),
}));

import * as cartApi from '@/api/cart';
import type { CartResponse } from '@/api/cartTypes';
import type { useCartStore as UseCartStoreType } from './cart';

const makeCart = (overrides: Partial<CartResponse> = {}): CartResponse => ({
  items: [],
  subtotal: 0,
  currency: 'RUB',
  expires_at: '2099-01-01T00:00:00Z',
  ...overrides,
});

describe('cart store', () => {
  let getState: () => ReturnType<typeof UseCartStoreType['getState']>;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.mock('@/api/cart', () => ({
      getCart: vi.fn(),
      addItem: vi.fn(),
      updateItem: vi.fn(),
      removeItem: vi.fn(),
      clearCart: vi.fn(),
    }));
    const mod = await import('./cart');
    getState = () => mod.useCartStore.getState();
  });

  it('начальное состояние: status idle, cart null', () => {
    const state = getState();
    expect(state.status).toBe('idle');
    expect(state.cart).toBeNull();
  });

  it('refresh: переходит в loading, затем ready с CartResponse', async () => {
    const cart = makeCart({ subtotal: 100 });
    (cartApi.getCart as Mock).mockResolvedValue(cart);

    await getState().refresh();

    const state = getState();
    expect(state.status).toBe('ready');
    expect(state.cart).toBe(cart);
  });

  it('addItem: заменяет cart ответом сервера', async () => {
    const cart = makeCart({ items: [{ line_id: 'line-1', menu_item_id: 1, size_option_id: null, modifier_ids: [], quantity: 1, unit_price: 100, line_total: 100, menu_item_snapshot: { name_ru: 'Кофе', name_en: 'Coffee', availability: 'available' }, size_snapshot: null, modifiers_snapshot: [] }] });
    (cartApi.addItem as Mock).mockResolvedValue(cart);

    await getState().addItem({ menu_item_id: 1, size_option_id: null, modifier_ids: [], quantity: 1 });

    expect(getState().cart?.items).toBe(cart.items);
  });

  it('updateQuantity: заменяет cart ответом сервера', async () => {
    const cart = makeCart({ subtotal: 200 });
    (cartApi.updateItem as Mock).mockResolvedValue(cart);

    await getState().updateQuantity('item-1', 2);

    expect(getState().cart).toBe(cart);
  });

  it('removeItem: заменяет cart ответом сервера', async () => {
    const cart = makeCart();
    (cartApi.removeItem as Mock).mockResolvedValue(cart);

    await getState().removeItem('item-1');

    expect(getState().cart).toBe(cart);
  });

  it('removeItem: при ошибке не меняет state и пробрасывает ошибку', async () => {
    (cartApi.getCart as Mock).mockResolvedValue(makeCart({ subtotal: 100 }));
    await getState().refresh();
    const before = getState().cart;

    (cartApi.removeItem as Mock).mockRejectedValue(new Error('HTTP 500'));

    await expect(getState().removeItem('item-1')).rejects.toThrow('500');
    expect(getState().cart).toBe(before);
  });

  it('itemCount: суммирует quantity всех позиций', async () => {
    const cart = makeCart({
      items: [
        { line_id: 'line-1', menu_item_id: 1, size_option_id: null, modifier_ids: [], quantity: 2, unit_price: 100, line_total: 200, menu_item_snapshot: { name_ru: '', name_en: '', availability: 'available' }, size_snapshot: null, modifiers_snapshot: [] },
        { line_id: 'line-2', menu_item_id: 2, size_option_id: null, modifier_ids: [], quantity: 3, unit_price: 100, line_total: 300, menu_item_snapshot: { name_ru: '', name_en: '', availability: 'available' }, size_snapshot: null, modifiers_snapshot: [] },
      ],
      subtotal: 500,
    });
    (cartApi.getCart as Mock).mockResolvedValue(cart);
    await getState().refresh();

    expect(getState().itemCount).toBe(5);
  });

  it('subtotal: возвращает subtotal из CartResponse без изменений', async () => {
    const cart = makeCart({ subtotal: 99999 });
    (cartApi.getCart as Mock).mockResolvedValue(cart);
    await getState().refresh();

    expect(getState().subtotal).toBe(99999);
  });
});
