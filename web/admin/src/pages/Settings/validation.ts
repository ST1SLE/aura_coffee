// Клиентская валидация настроек — mirrors backend правила (phase6 plan §414-429).
// Ключи ошибок совпадают с форматом parseFieldErrorsDeep (см. admin-settings.ts):
// 'shop_lat', 'free_delivery_threshold', 'working_hours.mon.open', и т.д.

import type { DayKey, WorkingHours, WorkingHoursDay } from '@/api/admin-settings';
import { DAYS } from '@/api/admin-settings';

// Строковое UI-представление формы (отдельно от wire-типа).
export interface SettingsFormState {
  shop_lat: string;
  shop_lon: string;
  delivery_radius_km: string;
  // Денежные поля в UI — рубли, строкой (type=number инпут).
  min_delivery_amount_rub: string;
  free_delivery_threshold_rub: string;
  delivery_fee_rub: string;
  loyalty_percent: string;
  default_prep_time_minutes: string;
  estimated_delivery_time_minutes: string;
  auto_close_minutes: string;
  working_hours: Record<DayKey, WorkingHoursDayInput>;
}

export interface WorkingHoursDayInput {
  closed: boolean;
  open: string; // 'HH:MM'
  close: string;
}

export type ErrorMap = Record<string, string>;

function num(s: string): number {
  return Number(s);
}

function isInt(s: string): boolean {
  if (s === '' || s === '-') return false;
  return /^-?\d+$/.test(s.trim());
}

function isFiniteNumber(s: string): boolean {
  if (s === '' || s === '-' || s === '.') return false;
  const n = Number(s);
  return Number.isFinite(n);
}

// 'HH:MM' → число минут с полуночи. -1 если невалидный формат.
export function parseTime(s: string): number {
  const m = /^(\d{2}):(\d{2})$/.exec(s);
  if (!m) return -1;
  const hh = Number(m[1]);
  const mm = Number(m[2]);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return -1;
  return hh * 60 + mm;
}

export function validateCoords(form: SettingsFormState): ErrorMap {
  const e: ErrorMap = {};
  if (!isFiniteNumber(form.shop_lat) || num(form.shop_lat) < -90 || num(form.shop_lat) > 90) {
    e.shop_lat = 'out_of_range';
  }
  if (!isFiniteNumber(form.shop_lon) || num(form.shop_lon) < -180 || num(form.shop_lon) > 180) {
    e.shop_lon = 'out_of_range';
  }
  return e;
}

export function validateDelivery(form: SettingsFormState): ErrorMap {
  const e: ErrorMap = {};

  if (
    !isFiniteNumber(form.delivery_radius_km) ||
    num(form.delivery_radius_km) < 0.1 ||
    num(form.delivery_radius_km) > 50
  ) {
    e.delivery_radius_km = 'out_of_range';
  }
  if (!isFiniteNumber(form.min_delivery_amount_rub) || num(form.min_delivery_amount_rub) < 0) {
    e.min_delivery_amount = 'out_of_range';
  }
  if (
    !isFiniteNumber(form.free_delivery_threshold_rub) ||
    num(form.free_delivery_threshold_rub) < 0
  ) {
    e.free_delivery_threshold = 'out_of_range';
  }
  if (!isFiniteNumber(form.delivery_fee_rub) || num(form.delivery_fee_rub) < 0) {
    e.delivery_fee = 'out_of_range';
  }

  // free_delivery_threshold ≥ min_delivery_amount.
  if (
    !e.min_delivery_amount &&
    !e.free_delivery_threshold &&
    num(form.free_delivery_threshold_rub) < num(form.min_delivery_amount_rub)
  ) {
    e.free_delivery_threshold = 'below_min_delivery';
  }

  return e;
}

export function validateLoyalty(form: SettingsFormState): ErrorMap {
  const e: ErrorMap = {};
  if (!isInt(form.loyalty_percent)) {
    e.loyalty_percent = 'out_of_range';
    return e;
  }
  const v = num(form.loyalty_percent);
  if (v < 0 || v > 100) e.loyalty_percent = 'out_of_range';
  return e;
}

export function validateTiming(form: SettingsFormState): ErrorMap {
  const e: ErrorMap = {};

  if (!isInt(form.default_prep_time_minutes) || num(form.default_prep_time_minutes) < 1) {
    e.default_prep_time_minutes = 'out_of_range';
  }
  if (
    !isInt(form.estimated_delivery_time_minutes) ||
    num(form.estimated_delivery_time_minutes) < 1
  ) {
    e.estimated_delivery_time_minutes = 'out_of_range';
  }
  if (!isInt(form.auto_close_minutes)) {
    e.auto_close_minutes = 'out_of_range';
  } else {
    const v = num(form.auto_close_minutes);
    if (v < 1 || v > 1440) e.auto_close_minutes = 'out_of_range';
  }
  return e;
}

export function validateWorkingHours(form: SettingsFormState): ErrorMap {
  const e: ErrorMap = {};
  for (const d of DAYS) {
    const row = form.working_hours[d];
    if (row.closed) continue;
    if (!row.open || !row.close) {
      e[`working_hours.${d}.open`] = 'empty_time';
      continue;
    }
    const openM = parseTime(row.open);
    const closeM = parseTime(row.close);
    if (openM < 0) {
      e[`working_hours.${d}.open`] = 'invalid_time';
      continue;
    }
    if (closeM < 0) {
      e[`working_hours.${d}.close`] = 'invalid_time';
      continue;
    }
    if (openM >= closeM) {
      e[`working_hours.${d}.open`] = 'open_after_close';
    }
  }
  return e;
}

export function validateAll(form: SettingsFormState): ErrorMap {
  return {
    ...validateCoords(form),
    ...validateDelivery(form),
    ...validateLoyalty(form),
    ...validateTiming(form),
    ...validateWorkingHours(form),
  };
}

export function isFormValid(form: SettingsFormState): boolean {
  return Object.keys(validateAll(form)).length === 0;
}

// ── Initial ↔ form mapping ───────────────────────────────────────────────────

import type { ShopSettingsResponse, ShopSettingsUpdate } from '@/api/admin-settings';
import { kopecksToRubles, toKopecks } from '@/api/admin-settings';

export function responseToForm(r: ShopSettingsResponse): SettingsFormState {
  const wh: Record<DayKey, WorkingHoursDayInput> = {} as Record<
    DayKey,
    WorkingHoursDayInput
  >;
  for (const d of DAYS) {
    const raw = r.working_hours?.[d] ?? null;
    wh[d] = raw
      ? { closed: false, open: raw.open, close: raw.close }
      : { closed: true, open: '', close: '' };
  }
  return {
    shop_lat: String(r.shop_lat),
    shop_lon: String(r.shop_lon),
    delivery_radius_km: String(r.delivery_radius_km),
    min_delivery_amount_rub: kopecksToRubles(r.min_delivery_amount),
    free_delivery_threshold_rub: kopecksToRubles(r.free_delivery_threshold),
    delivery_fee_rub: kopecksToRubles(r.delivery_fee),
    loyalty_percent: String(r.loyalty_percent),
    default_prep_time_minutes: String(r.default_prep_time_minutes),
    estimated_delivery_time_minutes: String(r.estimated_delivery_time_minutes),
    auto_close_minutes: String(r.auto_close_minutes),
    working_hours: wh,
  };
}

export function formToPayload(form: SettingsFormState): ShopSettingsUpdate {
  const wh: WorkingHours = {} as WorkingHours;
  for (const d of DAYS) {
    const row = form.working_hours[d];
    if (row.closed) {
      wh[d] = null;
    } else {
      const day: WorkingHoursDay = { open: row.open, close: row.close };
      wh[d] = day;
    }
  }
  return {
    shop_lat: Number(form.shop_lat),
    shop_lon: Number(form.shop_lon),
    delivery_radius_km: Number(form.delivery_radius_km),
    min_delivery_amount: toKopecks(Number(form.min_delivery_amount_rub)),
    free_delivery_threshold: toKopecks(Number(form.free_delivery_threshold_rub)),
    delivery_fee: toKopecks(Number(form.delivery_fee_rub)),
    loyalty_percent: Number(form.loyalty_percent),
    default_prep_time_minutes: Number(form.default_prep_time_minutes),
    estimated_delivery_time_minutes: Number(form.estimated_delivery_time_minutes),
    auto_close_minutes: Number(form.auto_close_minutes),
    working_hours: wh,
  };
}
