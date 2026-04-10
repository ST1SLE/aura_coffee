// Выбирает нужный язык: en → name_en, иначе → name_ru; откат на ru если en пустой
export function pickLang(ru: string, en: string, lang: string): string {
  if (lang === 'en') return en || ru;
  return ru;
}

// Конвертация копеек в рубли для отображения
export function formatPrice(kopecks: number): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
  }).format(kopecks / 100);
}

// Парсинг рублей из строки в копейки для отправки на сервер
export function rublesToKopecks(rubles: string): number {
  const val = parseFloat(rubles.replace(',', '.'));
  return Math.round(isNaN(val) ? 0 : val * 100);
}

// Конвертация копеек в строку рублей для поля ввода
export function kopecksToRublesStr(kopecks: number): string {
  return (kopecks / 100).toFixed(2);
}
