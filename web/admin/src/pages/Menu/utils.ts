// START_MODULE_CONTRACT
//   PURPOSE: Small helpers shared across Menu page subcomponents — locale
//            picker for bilingual fields and rubles<>kopecks converters.
//   SCOPE:   Used by CategoryList, MenuItemsTable, MenuItemFormDialog,
//            ModifiersPanel, ModifiersPicker, SizeOptionsEditor.
//   DEPENDS: Intl.NumberFormat (browser builtin).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §5.2 (kopecks),
//            AGENTS.md (bilingual RU/EN).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   pickLang          - choose RU or EN string with EN→RU fallback
//   formatPrice       - kopecks → "350,00 ₽" (ru-RU)
//   rublesToKopecks   - rubles string → integer kopecks (NaN-safe)
//   kopecksToRublesStr - kopecks → "350.00" string for input fields
// END_MODULE_MAP

// START_CONTRACT: pickLang
//   PURPOSE: Pick the locale-appropriate string from an RU/EN pair.
//   INPUTS:  ru: string, en: string, lang: string — current i18n.language tag
//   OUTPUTS: string — EN if lang==='en' (fallback to RU when EN empty), else RU.
//   SIDE_EFFECTS: none.
// END_CONTRACT: pickLang
// Выбирает нужный язык: en → name_en, иначе → name_ru; откат на ru если en пустой
export function pickLang(ru: string, en: string, lang: string): string {
  if (lang === 'en') return en || ru;
  return ru;
}

// START_CONTRACT: formatPrice
//   PURPOSE: Format kopecks as a Russian-locale RUB string with two decimals.
//   INPUTS:  kopecks: number
//   OUTPUTS: string
//   SIDE_EFFECTS: none.
// END_CONTRACT: formatPrice
// Конвертация копеек в рубли для отображения
export function formatPrice(kopecks: number): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
  }).format(kopecks / 100);
}

// START_CONTRACT: rublesToKopecks
//   PURPOSE: Parse a rubles string (accepts both '.' and ',' decimals) and
//            convert to integer kopecks for server payloads. NaN → 0.
//   INPUTS:  rubles: string
//   OUTPUTS: number — integer kopecks
//   SIDE_EFFECTS: none.
// END_CONTRACT: rublesToKopecks
// Парсинг рублей из строки в копейки для отправки на сервер
export function rublesToKopecks(rubles: string): number {
  const val = parseFloat(rubles.replace(',', '.'));
  return Math.round(isNaN(val) ? 0 : val * 100);
}

// START_CONTRACT: kopecksToRublesStr
//   PURPOSE: Convert kopecks to a fixed-2-decimal rubles string for input fields.
//   INPUTS:  kopecks: number
//   OUTPUTS: string
//   SIDE_EFFECTS: none.
// END_CONTRACT: kopecksToRublesStr
// Конвертация копеек в строку рублей для поля ввода
export function kopecksToRublesStr(kopecks: number): string {
  return (kopecks / 100).toFixed(2);
}
