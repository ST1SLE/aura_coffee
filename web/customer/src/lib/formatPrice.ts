// START_MODULE_CONTRACT
//   PURPOSE: Display-only price formatter — converts integer kopecks (server's
//            money unit) into a localized RUB currency string. Note AGENTS.md
//            "Prices always from server": this helper is for rendering only,
//            not for client-side computation.
//   SCOPE:   formatPrice.
//   DEPENDS: built-in Intl.NumberFormat.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5 cart pricing.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   formatPrice  - kopecks -> "199 ₽" / "₽199.00" string
// END_MODULE_MAP

// START_CONTRACT: formatPrice
//   PURPOSE: Render integer kopecks as a localized currency string.
//   INPUTS:  kopecks: number — integer kopecks (e.g. 19900 == 199 ₽)
//            locale: string  — BCP-47 tag (defaults to 'ru')
//   OUTPUTS: string — formatted currency, e.g. "199 ₽" or "199.50 ₽".
//   SIDE_EFFECTS: none. Display only — never use to compute prices client-side
//                 (AGENTS.md "Prices always from server").
//   LINKS:   PDD §5 cart pricing.
// END_CONTRACT: formatPrice
/**
 * Форматирует копейки в строку цены (₽).
 * @param kopecks целое число копеек
 * @param locale языковой тег (по умолчанию 'ru')
 */
export function formatPrice(kopecks: number, locale: string = 'ru'): string {
  const rubles = kopecks / 100;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: kopecks % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(rubles);
}
