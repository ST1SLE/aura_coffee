import { apiRequest } from './client';
import type { CartItemCreate, CartResponse } from './cartTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Cart REST client — thin wrappers over /api/v1/cart endpoints used
//            by the zustand cart store (store/cart.ts).
//   SCOPE:   getCart, addItem, updateItem, removeItem, clearCart.
//   DEPENDS: M-CORE-API (HTTP /api/v1/cart), ./client (apiRequest), ./cartTypes.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart; INV-014 —
//            server returns snapshot fields (name_ru/name_en, prices); UI must
//            render them as-is, never recompute prices client-side (AGENTS.md).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   getCart      - GET /cart — current cart with items + subtotal
//   addItem      - POST /cart/items — add a CartItemCreate, returns full cart
//   updateItem   - PATCH /cart/items/:id — change quantity, returns full cart
//   removeItem   - DELETE /cart/items/:id — returns full cart
//   clearCart    - DELETE /cart — returns empty cart
// END_MODULE_MAP

// START_CONTRACT: getCart
//   PURPOSE: Fetch the current user's cart.
//   INPUTS:  none.
//   OUTPUTS: Promise<CartResponse> — items + subtotal + currency + expires_at.
//   SIDE_EFFECTS: HTTP GET /api/v1/cart (authenticated). Throws ApiError.
// END_CONTRACT: getCart
export function getCart(): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart');
}

// START_CONTRACT: addItem
//   PURPOSE: Append a configured menu item (size + modifiers + qty) to the cart.
//   INPUTS:  payload: CartItemCreate — menu_item_id, size_option_id, modifier_ids,
//            quantity (1..99).
//   OUTPUTS: Promise<CartResponse> — refreshed cart from the server.
//   SIDE_EFFECTS: HTTP POST /api/v1/cart/items; throws ApiError. Server may
//                 return 410 if the cart expired.
//   LINKS:   PDD §5 cart; INV-014 (server returns snapshot fields).
// END_CONTRACT: addItem
export function addItem(payload: CartItemCreate): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// START_CONTRACT: updateItem
//   PURPOSE: Change the quantity of an existing cart line.
//   INPUTS:  itemId: string — line_id from CartItemResponse
//            body: { quantity: number } — new quantity (1..99)
//   OUTPUTS: Promise<CartResponse> — refreshed cart.
//   SIDE_EFFECTS: HTTP PATCH /api/v1/cart/items/:id; throws ApiError (notably
//                 410 on expired cart — UI shows toast and refetches).
//   LINKS:   CartPage.handleUpdate.
// END_CONTRACT: updateItem
export function updateItem(itemId: string, body: { quantity: number }): Promise<CartResponse> {
  return apiRequest<CartResponse>(`/api/v1/cart/items/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// START_CONTRACT: removeItem
//   PURPOSE: Remove a single line from the cart.
//   INPUTS:  itemId: string — line_id from CartItemResponse.
//   OUTPUTS: Promise<CartResponse> — cart without that line.
//   SIDE_EFFECTS: HTTP DELETE /api/v1/cart/items/:id; throws ApiError.
// END_CONTRACT: removeItem
export function removeItem(itemId: string): Promise<CartResponse> {
  return apiRequest<CartResponse>(`/api/v1/cart/items/${itemId}`, {
    method: 'DELETE',
  });
}

// START_CONTRACT: clearCart
//   PURPOSE: Empty the cart for the current user.
//   INPUTS:  none.
//   OUTPUTS: Promise<CartResponse> — empty cart record from the server.
//   SIDE_EFFECTS: HTTP DELETE /api/v1/cart; throws ApiError.
// END_CONTRACT: clearCart
export function clearCart(): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart', { method: 'DELETE' });
}
