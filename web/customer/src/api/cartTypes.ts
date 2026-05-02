import type { MenuItemAvailability, SizeLabel } from './menuTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Cart DTOs — the wire-format types returned by /api/v1/cart and the
//            CartItemCreate body. Snapshot fields (menu_item_snapshot, size_*,
//            modifiers_*) preserve historical names/prices on the server side
//            so a renamed/edited menu does not retroactively rewrite carts.
//            menu_item_snapshot.inventory_quantity is current stock metadata
//            for UX caps, not a historical price/name snapshot.
//   SCOPE:   Pure types; no runtime behavior.
//   DEPENDS: ./menuTypes (MenuItemAvailability, SizeLabel).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart;
//            INV-014 (snapshot semantics — also applies to orders).
//   ROLE:    TYPES
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   CartItemCreate          - POST /cart/items body shape
//   MenuItemCartSnapshot    - menu_item_snapshot field on a cart line
//   SizeSnapshot            - size_snapshot field (label + price in kopecks)
//   ModifierSnapshot        - one entry of modifiers_snapshot
//   CartItemResponse        - one cart line as returned by the server
//   CartResponse            - full cart payload (items + subtotal + expires_at)
// END_MODULE_MAP

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
  /** Current finite stock. null/undefined means unlimited/not tracked. */
  inventory_quantity?: number | null;
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
