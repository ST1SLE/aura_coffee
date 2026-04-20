import type { ShopSettingsResponse } from '@/api/admin-settings';
import type { SettingsFormState } from './validation';

export function baseResponse(): ShopSettingsResponse {
  return {
    shop_lat: 55.75,
    shop_lon: 37.62,
    delivery_radius_km: 5,
    min_delivery_amount: 50000,
    free_delivery_threshold: 150000,
    delivery_fee: 15000,
    loyalty_percent: 5,
    default_prep_time_minutes: 10,
    estimated_delivery_time_minutes: 30,
    auto_close_minutes: 60,
    working_hours: {
      mon: { open: '08:00', close: '22:00' },
      tue: { open: '08:00', close: '22:00' },
      wed: { open: '08:00', close: '22:00' },
      thu: { open: '08:00', close: '22:00' },
      fri: { open: '08:00', close: '22:00' },
      sat: { open: '10:00', close: '20:00' },
      sun: null,
    },
    updated_at: '2026-04-20T10:00:00Z',
  };
}

export function baseForm(): SettingsFormState {
  return {
    shop_lat: '55.75',
    shop_lon: '37.62',
    delivery_radius_km: '5',
    min_delivery_amount_rub: '500',
    free_delivery_threshold_rub: '1500',
    delivery_fee_rub: '150',
    loyalty_percent: '5',
    default_prep_time_minutes: '10',
    estimated_delivery_time_minutes: '30',
    auto_close_minutes: '60',
    working_hours: {
      mon: { closed: false, open: '08:00', close: '22:00' },
      tue: { closed: false, open: '08:00', close: '22:00' },
      wed: { closed: false, open: '08:00', close: '22:00' },
      thu: { closed: false, open: '08:00', close: '22:00' },
      fri: { closed: false, open: '08:00', close: '22:00' },
      sat: { closed: false, open: '10:00', close: '20:00' },
      sun: { closed: true, open: '', close: '' },
    },
  };
}
