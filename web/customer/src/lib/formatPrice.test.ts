import { describe, it, expect } from 'vitest';
import { formatPrice } from './formatPrice';

describe('formatPrice', () => {
  it('formats 0 kopecks as 0 rub (ru)', () => {
    const result = formatPrice(0, 'ru');
    expect(result).toMatch(/0/);
    expect(result).toMatch(/₽/);
  });

  it('formats 15000 kopecks as 150 rub (ru)', () => {
    const result = formatPrice(15000, 'ru');
    expect(result).toMatch(/150/);
    expect(result).toMatch(/₽/);
  });

  it('formats 123450 kopecks with kopeck fraction (ru)', () => {
    const result = formatPrice(123450, 'ru');
    // 1234.50 — must contain 1 234 and 50
    expect(result).toMatch(/1[\s\u00a0]?234/);
    expect(result).toMatch(/50/);
    expect(result).toMatch(/₽/);
  });

  it('formats 15000 kopecks in en locale', () => {
    const result = formatPrice(15000, 'en');
    expect(result).toMatch(/150/);
    // en-locale ICU may render as "RUB 150" or "₽150" depending on the runtime
    expect(result).toMatch(/₽|RUB/);
  });

  it('uses ru as default locale', () => {
    const result = formatPrice(15000);
    expect(result).toMatch(/150/);
    expect(result).toMatch(/₽/);
  });
});
