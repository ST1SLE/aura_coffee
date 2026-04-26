// Типы зеркалят Pydantic-схемы из services/core-api/core_api/schemas/menu.py
// При появлении OpenAPI-кодогенерации этот файл будет заменён целиком.

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin menu management — categories, items,
//            sizes, modifiers — plus per-item availability toggles used by
//            barista stop-list UX.
//   SCOPE:   Wraps /api/v1/admin/menu/*; mirrors core-api Pydantic schemas in
//            services/core-api/core_api/schemas/menu.py.
//   DEPENDS: ./client (authenticatedFetch, ApiError).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.4 menu CRUD,
//            INV-002 (admin scope enforced server-side; barista may only toggle
//            stop-list, full CRUD restricted at server).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError                 - re-export from ./client
//   Availability             - 'available' | 'stop_list' | 'archived'
//   CategoryType             - 'drink' | 'food' | 'merch' | 'modifier'
//   SizeLabel                - 'S' | 'M' | 'L'
//   CategoryResponse/...     - response/create/update DTOs (mirror Pydantic)
//   SizeOptionResponse/...   - size DTOs
//   ModifierResponse/...     - modifier DTOs
//   MenuItemResponse/...     - menu item DTOs
//   AvailabilityPatch        - PATCH body for stop-list toggle
//   listCategories           - GET /api/v1/admin/menu/categories
//   createCategory           - POST category (admin only server-side)
//   updateCategory           - PUT category (admin only)
//   deleteCategory           - DELETE category (admin only)
//   listItems                - GET /api/v1/admin/menu/items?category_id=
//   getItem                  - GET single menu item
//   createItem               - POST menu item (admin only)
//   updateItem               - PUT menu item (admin only)
//   deleteItem               - DELETE menu item (admin only)
//   setItemAvailability      - PATCH availability (admin OR barista — stop-list)
//   setItemModifiers         - PUT item-modifier link set (admin only)
//   listModifiers            - GET modifiers
//   createModifier           - POST modifier (admin only)
//   updateModifier           - PUT modifier (admin only)
//   deleteModifier           - DELETE modifier (admin only)
//   setModifierAvailability  - PATCH modifier availability (admin OR barista)
//   createSize/updateSize/deleteSize - size CRUD (admin only)
// END_MODULE_MAP

export { ApiError };

// ── Enums ────────────────────────────────────────────────────────────────────

export type Availability = 'available' | 'stop_list' | 'archived';

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

// START_CONTRACT: listCategories
//   PURPOSE: Fetch all menu categories for the admin/barista UI.
//   INPUTS:  none
//   OUTPUTS: Promise<CategoryResponse[]>
//   SIDE_EFFECTS: GET; throws ApiError on non-2xx.
//   LINKS:   INV-002.
// END_CONTRACT: listCategories
export const listCategories = (): Promise<CategoryResponse[]> =>
  json('/api/v1/admin/menu/categories');

// START_CONTRACT: createCategory
//   PURPOSE: Create a new menu category (admin only — server enforces).
//   INPUTS:  body: CategoryCreate
//   OUTPUTS: Promise<CategoryResponse>
//   SIDE_EFFECTS: POST; 403 if barista tries to call.
//   LINKS:   INV-002.
// END_CONTRACT: createCategory
export const createCategory = (body: CategoryCreate): Promise<CategoryResponse> =>
  post('/api/v1/admin/menu/categories', body);

// START_CONTRACT: updateCategory
//   PURPOSE: Update a category by id (admin only).
//   INPUTS:  id: number, body: CategoryUpdate (partial)
//   OUTPUTS: Promise<CategoryResponse>
//   SIDE_EFFECTS: PUT; 403 if not admin.
//   LINKS:   INV-002.
// END_CONTRACT: updateCategory
export const updateCategory = (
  id: number,
  body: CategoryUpdate,
): Promise<CategoryResponse> => put(`/api/v1/admin/menu/categories/${id}`, body);

// START_CONTRACT: deleteCategory
//   PURPOSE: Delete a category (admin only). 409 if it still has items.
//   INPUTS:  id: number
//   OUTPUTS: Promise<void>
//   SIDE_EFFECTS: DELETE; 409 on referential conflict.
//   LINKS:   INV-002.
// END_CONTRACT: deleteCategory
export const deleteCategory = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/categories/${id}`);

// ── Menu items ────────────────────────────────────────────────────────────────

// START_CONTRACT: listItems
//   PURPOSE: List menu items, optionally filtered by category.
//   INPUTS:  params?: { categoryId?: number }
//   OUTPUTS: Promise<MenuItemResponse[]>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002.
// END_CONTRACT: listItems
export const listItems = (params?: {
  categoryId?: number;
}): Promise<MenuItemResponse[]> => {
  const qs = params?.categoryId != null ? `?category_id=${params.categoryId}` : '';
  return json(`/api/v1/admin/menu/items${qs}`);
};

// START_CONTRACT: getItem
//   PURPOSE: Fetch a single menu item.
//   INPUTS:  id: number
//   OUTPUTS: Promise<MenuItemResponse>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002.
// END_CONTRACT: getItem
export const getItem = (id: number): Promise<MenuItemResponse> =>
  json(`/api/v1/admin/menu/items/${id}`);

// START_CONTRACT: createItem
//   PURPOSE: Create a new menu item (admin only).
//   INPUTS:  body: MenuItemCreate
//   OUTPUTS: Promise<MenuItemResponse>
//   SIDE_EFFECTS: POST; 403 if barista calls; 422 on validation.
//   LINKS:   INV-002.
// END_CONTRACT: createItem
export const createItem = (body: MenuItemCreate): Promise<MenuItemResponse> =>
  post('/api/v1/admin/menu/items', body);

// START_CONTRACT: updateItem
//   PURPOSE: Update a menu item (admin only).
//   INPUTS:  id: number, body: MenuItemUpdate
//   OUTPUTS: Promise<MenuItemResponse>
//   SIDE_EFFECTS: PUT; 403/422.
//   LINKS:   INV-002.
// END_CONTRACT: updateItem
export const updateItem = (
  id: number,
  body: MenuItemUpdate,
): Promise<MenuItemResponse> => put(`/api/v1/admin/menu/items/${id}`, body);

// START_CONTRACT: deleteItem
//   PURPOSE: Delete a menu item (admin only).
//   INPUTS:  id: number
//   OUTPUTS: Promise<void>
//   SIDE_EFFECTS: DELETE.
//   LINKS:   INV-002.
// END_CONTRACT: deleteItem
export const deleteItem = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/items/${id}`);

// START_CONTRACT: setItemAvailability
//   PURPOSE: Toggle stop-list flag for a menu item — accessible to admin AND
//            barista (the only menu mutation barista is allowed to perform).
//   INPUTS:  id: number, available: boolean
//   OUTPUTS: Promise<MenuItemResponse> — fresh availability state from server.
//   SIDE_EFFECTS: PATCH.
//   LINKS:   INV-002 (server allows admin+barista here, denies courier),
//            INV-010 (role isolation — barista cannot edit anything else).
// END_CONTRACT: setItemAvailability
export const setItemAvailability = (
  id: number,
  available: boolean,
): Promise<MenuItemResponse> =>
  patch(`/api/v1/admin/menu/items/${id}/availability`, { available });

// START_CONTRACT: setItemModifiers
//   PURPOSE: Replace the modifier set linked to a menu item (admin only).
//   INPUTS:  id: number, modifier_ids: number[]
//   OUTPUTS: Promise<MenuItemResponse>
//   SIDE_EFFECTS: PUT; 403 if barista calls.
//   LINKS:   INV-002.
// END_CONTRACT: setItemModifiers
export const setItemModifiers = (
  id: number,
  modifier_ids: number[],
): Promise<MenuItemResponse> =>
  put(`/api/v1/admin/menu/items/${id}/modifiers`, { modifier_ids });

// ── Modifiers ─────────────────────────────────────────────────────────────────

// START_CONTRACT: listModifiers
//   PURPOSE: Fetch all modifiers for picker UIs and stop-list management.
//   INPUTS:  none
//   OUTPUTS: Promise<ModifierResponse[]>
//   SIDE_EFFECTS: GET.
//   LINKS:   INV-002.
// END_CONTRACT: listModifiers
export const listModifiers = (): Promise<ModifierResponse[]> =>
  json('/api/v1/admin/menu/modifiers');

// START_CONTRACT: createModifier
//   PURPOSE: Create a new modifier (admin only).
//   INPUTS:  body: ModifierCreate
//   OUTPUTS: Promise<ModifierResponse>
//   SIDE_EFFECTS: POST; 403/422.
//   LINKS:   INV-002.
// END_CONTRACT: createModifier
export const createModifier = (body: ModifierCreate): Promise<ModifierResponse> =>
  post('/api/v1/admin/menu/modifiers', body);

// START_CONTRACT: updateModifier
//   PURPOSE: Update a modifier (admin only).
//   INPUTS:  id: number, body: ModifierUpdate
//   OUTPUTS: Promise<ModifierResponse>
//   SIDE_EFFECTS: PUT.
//   LINKS:   INV-002.
// END_CONTRACT: updateModifier
export const updateModifier = (
  id: number,
  body: ModifierUpdate,
): Promise<ModifierResponse> => put(`/api/v1/admin/menu/modifiers/${id}`, body);

// START_CONTRACT: deleteModifier
//   PURPOSE: Delete a modifier (admin only).
//   INPUTS:  id: number
//   OUTPUTS: Promise<void>
//   SIDE_EFFECTS: DELETE.
//   LINKS:   INV-002.
// END_CONTRACT: deleteModifier
export const deleteModifier = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/modifiers/${id}`);

// START_CONTRACT: setModifierAvailability
//   PURPOSE: Toggle stop-list flag on a modifier — admin OR barista (parallel
//            to setItemAvailability).
//   INPUTS:  id: number, available: boolean
//   OUTPUTS: Promise<ModifierResponse>
//   SIDE_EFFECTS: PATCH.
//   LINKS:   INV-002, INV-010.
// END_CONTRACT: setModifierAvailability
export const setModifierAvailability = (
  id: number,
  available: boolean,
): Promise<ModifierResponse> =>
  patch(`/api/v1/admin/menu/modifiers/${id}/availability`, { available });

// ── Sizes ─────────────────────────────────────────────────────────────────────

// START_CONTRACT: createSize
//   PURPOSE: Add a size option (S/M/L) to a menu item (admin only).
//   INPUTS:  body: SizeOptionCreate
//   OUTPUTS: Promise<SizeOptionResponse>
//   SIDE_EFFECTS: POST; 409 on duplicate label.
//   LINKS:   INV-002.
// END_CONTRACT: createSize
export const createSize = (body: SizeOptionCreate): Promise<SizeOptionResponse> =>
  post('/api/v1/admin/menu/sizes', body);

// START_CONTRACT: updateSize
//   PURPOSE: Update a size option (admin only).
//   INPUTS:  id: number, body: SizeOptionUpdate
//   OUTPUTS: Promise<SizeOptionResponse>
//   SIDE_EFFECTS: PUT.
//   LINKS:   INV-002.
// END_CONTRACT: updateSize
export const updateSize = (
  id: number,
  body: SizeOptionUpdate,
): Promise<SizeOptionResponse> => put(`/api/v1/admin/menu/sizes/${id}`, body);

// START_CONTRACT: deleteSize
//   PURPOSE: Delete a size option (admin only).
//   INPUTS:  id: number
//   OUTPUTS: Promise<void>
//   SIDE_EFFECTS: DELETE.
//   LINKS:   INV-002.
// END_CONTRACT: deleteSize
export const deleteSize = (id: number): Promise<void> =>
  del(`/api/v1/admin/menu/sizes/${id}`);
