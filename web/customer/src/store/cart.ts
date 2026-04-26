// Хранилище корзины — zustand
import { create } from 'zustand';
import * as cartApi from '@/api/cart';
import type { CartItemCreate, CartResponse } from '@/api/cartTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Zustand store for the cart — wraps api/cart with derived fields
//            (itemCount, subtotal, items, currency, expiresAt) so components
//            can subscribe to a flat shape without repeatedly walking cart.items.
//            Mutations are optimistic-rollback: on API failure the previous
//            cart state is restored and the error rethrown for the page to
//            handle (e.g. 410 EXPIRED -> CartPage shows toast + refetch).
//   SCOPE:   useCartStore (the zustand hook). No private helpers exported.
//   DEPENDS: zustand, @/api/cart (REST), @/api/cartTypes.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart;
//            INV-014 (server returns snapshot fields — store keeps them as-is).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   useCartStore  - zustand hook returning CartState (status + data + actions)
// END_MODULE_MAP

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
  clearCart: () => Promise<void>;
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

// START_CONTRACT: useCartStore
//   PURPOSE: zustand hook exposing reactive cart state and the four mutating
//            actions. Components select the slice they need (e.g.
//            useCartStore((s) => s.addItem)) so re-renders stay narrow.
//   INPUTS:  none — call as a hook.
//   OUTPUTS: CartState — { status, cart, itemCount, subtotal, items, currency,
//            expiresAt, refresh, addItem, updateQuantity, removeItem, clearCart }.
//   SIDE_EFFECTS: refresh()/addItem()/updateQuantity()/removeItem()/clearCart()
//                 perform HTTP calls via api/cart and may throw ApiError
//                 (notably 410 on expired cart — CartPage handles).
//   LINKS:   PDD §5 cart; INV-014 server snapshots.
// END_CONTRACT: useCartStore
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

  clearCart: () =>
    mutate(set, get, () => cartApi.clearCart()),
}));
