// START_MODULE_CONTRACT
//   PURPOSE: Public menu DTOs — wire-format types returned by GET /api/v1/menu.
//            Includes both bilingual fields (name_ru/name_en) and a
//            server-pre-resolved `name`/`description` per current locale.
//   SCOPE:   Pure types; no runtime behavior.
//   DEPENDS: none.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu.
//   ROLE:    TYPES
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CategoryType            - 'drink' | 'food' | 'merch' | 'modifier'
//   MenuItemAvailability    - 'available' | 'stop_list' | 'archived'
//   SizeLabel               - 'S' | 'M' | 'L'
//   PublicMenuSizeOption    - one size variant for an item
//   PublicMenuModifier      - one modifier (e.g. extra shot)
//   PublicMenuItem          - one menu item with sizes + modifiers
//   PublicCategory          - menu category with items
//   PublicMenuResponse      - top-level GET /menu payload
// END_MODULE_MAP

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
