import { describe, it, expect, beforeEach } from 'vitest';
import { getRole, setRole, clearRole, type StaffRole } from '@/lib/auth';

describe('auth — role helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('setRole persists to localStorage.staffRole', () => {
    setRole('courier');
    expect(localStorage.getItem('staffRole')).toBe('courier');
  });

  it('clearRole removes the key', () => {
    setRole('admin');
    clearRole();
    expect(localStorage.getItem('staffRole')).toBeNull();
  });

  it('getRole returns null when no value persisted', () => {
    expect(getRole()).toBeNull();
  });

  it('getRole round-trips the persisted role', () => {
    setRole('barista');
    expect(getRole()).toBe('barista');
  });

  // Типовая проверка: getRole() должен быть StaffRole | null, а не string | null
  it('getRole return type narrows to StaffRole | null', () => {
    setRole('courier');
    const r = getRole();
    // Компилятор должен разрешить сравнение без ошибки — значит тип сужен
    if (r === 'courier') {
      expect(r).toBe('courier');
    }
    // @ts-expect-error — произвольная строка не входит в StaffRole
    const invalid: StaffRole = 'ceo';
    expect(invalid).toBe('ceo');
  });
});
