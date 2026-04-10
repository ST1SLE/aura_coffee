import { apiRequest } from './client';
import type { CategoryResponse, MenuItemResponse } from './menuTypes';

export function listCategories(): Promise<CategoryResponse[]> {
  return apiRequest<CategoryResponse[]>('/api/v1/menu/categories');
}

export function listMenuItems(params?: { categoryId?: number }): Promise<MenuItemResponse[]> {
  const url = params?.categoryId != null
    ? `/api/v1/menu/items?category_id=${params.categoryId}`
    : '/api/v1/menu/items';
  return apiRequest<MenuItemResponse[]>(url);
}

export function getMenuItem(id: number): Promise<MenuItemResponse> {
  return apiRequest<MenuItemResponse>(`/api/v1/menu/items/${id}`);
}
