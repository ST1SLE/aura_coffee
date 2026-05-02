import { test, expect, beforeAll } from 'vitest';
import i18n from '@/i18n/config';

const COURIER_KEYS = [
  'courier.tabs.available',
  'courier.tabs.mine',
  'courier.actions.take',
  'courier.actions.pickup',
  'courier.actions.deliver',
  'courier.empty.available',
  'courier.empty.mine',
  'courier.errors.alreadyTaken',
  'courier.errors.forbidden',
  'courier.errors.loadFailed',
  'courier.fields.requestedAsap',
  'courier.fields.total',
  'courier.fields.address',
  'courier.fields.addressHidden',
];

beforeAll(async () => {
  await i18n.changeLanguage('ru');
});

for (const lng of ['ru', 'en'] as const) {
  test(`courier namespace keys resolve under lng=${lng}`, async () => {
    await i18n.changeLanguage(lng);
    for (const key of COURIER_KEYS) {
      const value = i18n.t(key);
      expect(value, `${key} under ${lng}`).toBeTruthy();
      expect(value, `${key} under ${lng}`).not.toBe(key);
    }
  });
}
