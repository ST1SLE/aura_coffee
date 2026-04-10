export type CategoryType = 'drink' | 'food' | 'merch' | 'modifier';
export type MenuItemAvailability = 'available' | 'stop_list' | 'archived';
export type SizeLabel = 'S' | 'M' | 'L';

export interface CategoryResponse {
  id: number;
  type: CategoryType;
  name_ru: string;
  name_en: string;
  sort_order: number;
  is_visible: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ModifierResponse {
  id: number;
  name_ru: string;
  name_en: string;
  /** Цена в копейках */
  price: number;
  available: boolean;
  sort_order: number;
}

export interface SizeOptionResponse {
  id: number;
  menu_item_id: number;
  label: SizeLabel;
  /** Цена в копейках */
  price: number;
  available: boolean;
}

export interface MenuItemResponse {
  id: number;
  category_id: number;
  name_ru: string;
  name_en: string;
  description_ru: string | null;
  description_en: string | null;
  /** Базовая цена в копейках */
  base_price: number;
  image_url: string | null;
  available: boolean;
  archived: boolean;
  sort_order: number;
  created_at: string | null;
  updated_at: string | null;
  size_options: SizeOptionResponse[];
  modifiers: ModifierResponse[];
  availability: MenuItemAvailability;
}
