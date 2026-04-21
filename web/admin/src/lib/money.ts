// Форматирует сумму в копейках как локализованную валютную строку RUB.
// Используется дашбордом и другими admin-страницами phase 6.
//
// Цены в БД — целые копейки (PDD §5.2). UI показывает рубли с двумя
// десятичными знаками. Intl.NumberFormat берёт на себя разделители и
// знак валюты в соответствии с выбранной локалью.

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
