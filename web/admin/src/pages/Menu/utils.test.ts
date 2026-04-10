import { describe, test, expect } from 'vitest';
import { pickLang, formatPrice, rublesToKopecks, kopecksToRublesStr } from './utils';

describe('pickLang', () => {
  test('pickLang returns ru for ru, en for en, falls back to ru', () => {
    expect(pickLang('Кофе', 'Coffee', 'en')).toBe('Coffee');
    expect(pickLang('Кофе', 'Coffee', 'ru')).toBe('Кофе');
    // Откат на ru, если en пустой
    expect(pickLang('Кофе', '', 'en')).toBe('Кофе');
  });

  test('pickLang falls back to ru for unknown lang', () => {
    expect(pickLang('Кофе', 'Coffee', 'de')).toBe('Кофе');
  });
});

describe('formatPrice', () => {
  test('форматирует копейки в рубли', () => {
    const result = formatPrice(35000);
    expect(result).toContain('350');
  });
});

describe('rublesToKopecks / kopecksToRublesStr', () => {
  test('конвертация в обе стороны', () => {
    expect(rublesToKopecks('350.00')).toBe(35000);
    expect(kopecksToRublesStr(35000)).toBe('350.00');
  });
});
