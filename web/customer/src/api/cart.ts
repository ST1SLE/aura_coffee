import { apiRequest } from './client';
import type { CartItemCreate, CartResponse } from './cartTypes';

export function getCart(): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart');
}

export function addItem(payload: CartItemCreate): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function updateItem(itemId: string, body: { quantity: number }): Promise<CartResponse> {
  return apiRequest<CartResponse>(`/api/v1/cart/items/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function removeItem(itemId: string): Promise<CartResponse> {
  return apiRequest<CartResponse>(`/api/v1/cart/items/${itemId}`, {
    method: 'DELETE',
  });
}

export function clearCart(): Promise<CartResponse> {
  return apiRequest<CartResponse>('/api/v1/cart', { method: 'DELETE' });
}
