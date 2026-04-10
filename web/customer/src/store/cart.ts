// Хранилище корзины — zustand
import { create } from 'zustand';
import * as cartApi from '@/api/cart';
import type { CartItemCreate, CartResponse } from '@/api/cartTypes';

type CartStatus = 'idle' | 'loading' | 'ready' | 'error';

interface CartState {
  status: CartStatus;
  cart: CartResponse | null;
  // Производные поля (пересчитываются при каждом set)
  itemCount: number;
  subtotal: number;
  items: CartResponse['items'];
  currency: string;
  expiresAt: string | null;
  // Действия
  refresh: () => Promise<void>;
  addItem: (payload: CartItemCreate) => Promise<void>;
  updateQuantity: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
}

/** Вычисляет производные поля из cart */
function derived(cart: CartResponse | null) {
  return {
    itemCount: cart?.items.reduce((sum, it) => sum + it.quantity, 0) ?? 0,
    subtotal: cart?.subtotal ?? 0,
    items: cart?.items ?? [],
    currency: cart?.currency ?? 'RUB',
    expiresAt: cart?.expires_at ?? null,
  };
}

/** Выполняет мутацию: при ошибке откатывает состояние и пробрасывает */
async function mutate(
  set: (fn: (s: CartState) => Partial<CartState>) => void,
  get: () => CartState,
  action: () => Promise<CartResponse>,
): Promise<void> {
  const prev = get().cart;
  try {
    const cart = await action();
    set(() => ({ cart, status: 'ready', ...derived(cart) }));
  } catch (err) {
    set(() => ({ cart: prev, ...derived(prev) }));
    throw err;
  }
}

export const useCartStore = create<CartState>((set, get) => ({
  status: 'idle',
  cart: null,
  ...derived(null),

  async refresh() {
    set(() => ({ status: 'loading' }));
    try {
      const cart = await cartApi.getCart();
      set(() => ({ cart, status: 'ready', ...derived(cart) }));
    } catch {
      set(() => ({ status: 'error' }));
      throw new Error('Failed to load cart');
    }
  },

  addItem: (payload) =>
    mutate(set, get, () => cartApi.addItem(payload)),

  updateQuantity: (itemId, quantity) =>
    mutate(set, get, () => cartApi.updateItem(itemId, { quantity })),

  removeItem: (itemId) =>
    mutate(set, get, () => cartApi.removeItem(itemId)),
}));
