import { describe, test, expect } from 'vitest';
import { formatKopecks } from './money';

// Intl.NumberFormat в jsdom даёт разный whitespace (NBSP vs regular) —
// assert'им только ключевые цифровые группы и валютный маркер.

describe('formatKopecks', () => {
  test('ru-locale: 1 234 500 копеек содержит 12, 345 и валютный маркер', () => {
    const out = formatKopecks(1234500, 'ru');
    expect(out).toMatch(/12/);
    expect(out).toMatch(/345/);
    expect(out).toMatch(/₽|RUB/);
  });

  test('ru-locale: два десятичных знака присутствуют', () => {
    const out = formatKopecks(1234500, 'ru');
    // "12 345,00 ₽" — запятая или точка как десятичный разделитель
    expect(out).toMatch(/[,.]00/);
  });

  test('ru-locale: 0 копеек отрисовывается с валютным маркером', () => {
    const out = formatKopecks(0, 'ru');
    expect(out).toMatch(/0/);
    expect(out).toMatch(/₽|RUB/);
  });

  test('en-locale: не падает и возвращает строку с числом и валютой', () => {
    const out = formatKopecks(1234500, 'en');
    expect(typeof out).toBe('string');
    expect(out.length).toBeGreaterThan(0);
    expect(out).toMatch(/12/);
    expect(out).toMatch(/345/);
    expect(out).toMatch(/₽|RUB/);
  });

  test('детерминированность: один и тот же ввод даёт равные результаты', () => {
    expect(formatKopecks(9999, 'ru')).toBe(formatKopecks(9999, 'ru'));
    expect(formatKopecks(9999, 'en')).toBe(formatKopecks(9999, 'en'));
  });
});
