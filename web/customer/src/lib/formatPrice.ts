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
