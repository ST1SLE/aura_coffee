import { test, expect } from 'vitest';
import ruCommon from '../ru/common.json';
import enCommon from '../en/common.json';

// Рекурсивно разворачивает вложенный объект в список точечных ключей
function flattenKeys(obj: object, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      keys.push(...flattenKeys(v as object, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

test('ru and en locale keys are identical', () => {
  const ruKeys = flattenKeys(ruCommon).sort();
  const enKeys = flattenKeys(enCommon).sort();
  expect(ruKeys).toEqual(enKeys);
});
