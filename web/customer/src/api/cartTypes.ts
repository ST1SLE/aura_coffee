import type { MenuItemAvailability, SizeLabel } from './menuTypes';

export interface CartItemCreate {
  menu_item_id: number;
  size_option_id: number | null;
  modifier_ids: number[];
  /** Количество: 1..99 */
  quantity: number;
}

export interface MenuItemCartSnapshot {
  name_ru: string;
  name_en: string;
  availability: MenuItemAvailability;
}

export interface SizeSnapshot {
  label: SizeLabel;
  /** Цена в копейках */
  price: number;
}

export interface ModifierSnapshot {
  id: number;
  name_ru: string;
  name_en: string;
  /** Цена в копейках */
  price: number;
}

export interface CartItemResponse {
  line_id: string;
  menu_item_id: number;
  size_option_id: number | null;
  modifier_ids: number[];
  quantity: number;
  /** Цена единицы в копейках */
  unit_price: number;
  /** Итог строки в копейках */
  line_total: number;
  menu_item_snapshot: MenuItemCartSnapshot;
  size_snapshot: SizeSnapshot | null;
  modifiers_snapshot: ModifierSnapshot[];
}

export interface CartResponse {
  items: CartItemResponse[];
  /** Итого в копейках */
  subtotal: number;
  currency: 'RUB';
  expires_at: string;
}
