// Типы зеркалят Pydantic-схемы из services/core-api/core_api/schemas/menu.py
// При появлении OpenAPI-кодогенерации этот файл будет заменён целиком.

import { authenticatedFetch, ApiError } from './client';

export { ApiError };

// ── Enums ────────────────────────────────────────────────────────────────────

export type Availability = 'AVAILABLE' | 'STOP_LIST' | 'ARCHIVED';

export type CategoryType = 'drink' | 'food' | 'merch' | 'modifier';

export type SizeLabel = 'S' | 'M' | 'L';

// ── Category ─────────────────────────────────────────────────────────────────

export interface CategoryResponse {
  id: number;
  type: CategoryType;
  name_ru: string;
  name_en: string;
  sort_order: number;
  is_visible: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CategoryCreate {
  type: CategoryType;
  name_ru: string;
  name_en: string;
  sort_order: number;
  is_visible: boolean;
}

export interface CategoryUpdate {
  type?: CategoryType;
  name_ru?: string;
  name_en?: string;
  sort_order?: number;
  is_visible?: boolean;
}

// ── SizeOption ────────────────────────────────────────────────────────────────

export interface SizeOptionResponse {
  id: number;
  menu_item_id: number;
  label: SizeLabel;
  price: number;
  available: boolean;
}

export interface SizeOptionCreate {
  menu_item_id: number;
  label: SizeLabel;
  price: number;
  available?: boolean;
}

export interface SizeOptionUpdate {
  label?: SizeLabel;
  price?: number;
  available?: boolean;
}

// ── Modifier ──────────────────────────────────────────────────────────────────

export interface ModifierResponse {
  id: number;
  name_ru: string;
  name_en: string;
  price: number;
  available: boolean;
  sort_order: number;
}

export interface ModifierCreate {
  name_ru: string;
  name_en: string;
  price: number;
  available?: boolean;
  sort_order?: number;
}

export interface ModifierUpdate {
  name_ru?: string;
  name_en?: string;
  price?: number;
  available?: boolean;
  sort_order?: number;
}

// ── MenuItem ──────────────────────────────────────────────────────────────────

export interface MenuItemResponse {
  id: number;
  category_id: number;
  name_ru: string;
  name_en: string;
  description_ru: string | null;
  description_en: string | null;
  base_price: number;
  image_url: string | null;
  available: boolean;
  archived: boolean;
  availability: Availability;
  sort_order: number;
  size_options: SizeOptionResponse[];
  modifiers: ModifierResponse[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MenuItemCreate {
  category_id: number;
  name_ru: string;
  name_en: string;
  description_ru?: string | null;
  description_en?: string | null;
  base_price: number;
  image_url?: string | null;
  available?: boolean;
  archived?: boolean;
  sort_order?: number;
}

export interface MenuItemUpdate {
  category_id?: number;
  name_ru?: string;
  name_en?: string;
  description_ru?: string | null;
  description_en?: string | null;
  base_price?: number;
  image_url?: string | null;
  available?: boolean;
  archived?: boolean;
  sort_order?: number;
}

// ── Availability PATCH ────────────────────────────────────────────────────────

export interface AvailabilityPatch {
  available: boolean;
}

// ── helpers ───────────────────────────────────────────────────────────────────

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return json<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function put<T>(path: string, body: unknown): Promise<T> {
  return json<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function patch<T>(path: string, body: unknown): Promise<T> {
  return json<T>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function del(path: string): Promise<void> {
  return json<void>(path, { method: 'DELETE' });
}

// ── Categories ────────────────────────────────────────────────────────────────

export const listCategories = (): Promise<CategoryResponse[]> =>
  json('/api/v1/admin/menu/categories');

export const createCategory = (body: CategoryCreate): Promise<CategoryResponse> =>
  post('/api/v1/admin/menu/categories', body);

export const updateCategory = (
  id: number,
  body: CategoryUpdate,
): Promise<CategoryResponse> => put(`/api/v1/admin/menu/categories/${id}`, body);

export const deleteCategory = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/categories/${id}`);

// ── Menu items ────────────────────────────────────────────────────────────────

export const listItems = (params?: {
  categoryId?: number;
}): Promise<MenuItemResponse[]> => {
  const qs = params?.categoryId != null ? `?category_id=${params.categoryId}` : '';
  return json(`/api/v1/admin/menu/items${qs}`);
};

export const getItem = (id: number): Promise<MenuItemResponse> =>
  json(`/api/v1/admin/menu/items/${id}`);

export const createItem = (body: MenuItemCreate): Promise<MenuItemResponse> =>
  post('/api/v1/admin/menu/items', body);

export const updateItem = (
  id: number,
  body: MenuItemUpdate,
): Promise<MenuItemResponse> => put(`/api/v1/admin/menu/items/${id}`, body);

export const deleteItem = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/items/${id}`);

export const setItemAvailability = (
  id: number,
  available: boolean,
): Promise<MenuItemResponse> =>
  patch(`/api/v1/admin/menu/items/${id}/availability`, { available });

// ── Modifiers ─────────────────────────────────────────────────────────────────

export const listModifiers = (): Promise<ModifierResponse[]> =>
  json('/api/v1/admin/menu/modifiers');

export const createModifier = (body: ModifierCreate): Promise<ModifierResponse> =>
  post('/api/v1/admin/menu/modifiers', body);

export const updateModifier = (
  id: number,
  body: ModifierUpdate,
): Promise<ModifierResponse> => put(`/api/v1/admin/menu/modifiers/${id}`, body);

export const deleteModifier = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/modifiers/${id}`);

export const setModifierAvailability = (
  id: number,
  available: boolean,
): Promise<ModifierResponse> =>
  patch(`/api/v1/admin/menu/modifiers/${id}/availability`, { available });

// ── Sizes ─────────────────────────────────────────────────────────────────────

export const createSize = (body: SizeOptionCreate): Promise<SizeOptionResponse> =>
  post('/api/v1/admin/menu/sizes', body);

export const updateSize = (
  id: number,
  body: SizeOptionUpdate,
): Promise<SizeOptionResponse> => put(`/api/v1/admin/menu/sizes/${id}`, body);

export const deleteSize = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/sizes/${id}`);
