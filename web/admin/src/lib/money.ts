// Форматирует сумму в копейках как локализованную валютную строку RUB.
// Используется дашбордом и другими admin-страницами phase 6.
//
// Цены в БД — целые копейки (PDD §5.2). UI показывает рубли с двумя
// десятичными знаками. Intl.NumberFormat берёт на себя разделители и
// знак валюты в соответствии с выбранной локалью.

// START_MODULE_CONTRACT
//   PURPOSE: Locale-aware kopecks→RUB currency formatter shared by the dashboard
//            and other admin surfaces.
//   SCOPE:   Single pure formatter; complements api/admin-settings.ts converters
//            (which are non-locale string forms for inputs).
//   DEPENDS: Intl.NumberFormat (browser-builtin).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §5.2 (money is kopecks).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   formatKopecks - kopecks number → "350,00 ₽" (ru) / "RUB 350.00" (en)
// END_MODULE_MAP

// START_CONTRACT: formatKopecks
//   PURPOSE: Format a kopecks integer as a localized RUB currency string.
//   INPUTS:  kopecks: number, locale: 'ru' | 'en'
//   OUTPUTS: string
//   SIDE_EFFECTS: none.
// END_CONTRACT: formatKopecks
export function formatKopecks(kopecks: number, locale: 'ru' | 'en'): string {
  const rubles = kopecks / 100;
  const tag = locale === 'ru' ? 'ru-RU' : 'en-US';
  return new Intl.NumberFormat(tag, {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rubles);
}
