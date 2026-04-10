export type CategoryType = 'drink' | 'food' | 'merch' | 'modifier';
export type MenuItemAvailability = 'available' | 'stop_list' | 'archived';
export type SizeLabel = 'S' | 'M' | 'L';

export interface PublicMenuSizeOption {
  id: number;
  label: SizeLabel;
  /** Цена в копейках */
  price: number;
  available: boolean;
}

export interface PublicMenuModifier {
  id: number;
  /** Уже разрешённое серверным языковым контекстом название */
  name: string;
  name_ru: string;
  name_en: string;
  /** Цена в копейках */
  price: number;
  available: boolean;
}

export interface PublicMenuItem {
  id: number;
  category_id: number;
  /** Уже разрешённое серверным языковым контекстом название */
  name: string;
  name_ru: string;
  name_en: string;
  /** Уже разрешённое серверным языковым контекстом описание */
  description: string | null;
  description_ru: string | null;
  description_en: string | null;
  /** Базовая цена в копейках */
  base_price: number;
  image_url: string | null;
  available: boolean;
  sort_order: number;
  size_options: PublicMenuSizeOption[];
  modifiers: PublicMenuModifier[];
}

export interface PublicCategory {
  id: number;
  type: CategoryType;
  /** Уже разрешённое серверным языковым контекстом название */
  name: string;
  name_ru: string;
  name_en: string;
  sort_order: number;
  items: PublicMenuItem[];
}

export interface PublicMenuResponse {
  categories: PublicCategory[];
}
