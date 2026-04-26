// Клиентская валидация настроек — mirrors backend правила (phase6 plan §414-429).
// Ключи ошибок совпадают с форматом parseFieldErrorsDeep (см. admin-settings.ts):
// 'shop_lat', 'free_delivery_threshold', 'working_hours.mon.open', и т.д.

import type { DayKey, WorkingHours, WorkingHoursDay } from '@/api/admin-settings';
import { DAYS } from '@/api/admin-settings';

// START_MODULE_CONTRACT
//   PURPOSE: Client-side validators for the SettingsPage form plus form↔wire
//            mapping helpers. Mirrors backend invariants (phase6 plan §414-429)
//            so the user gets fast feedback before hitting 422; server is
//            still the source of truth for validation.
//   SCOPE:   Used only by SettingsPage and Section* sub-forms; tests pull from testUtils.
//   DEPENDS: @/api/admin-settings (types + DAYS + kopeck converters).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   SettingsFormState     - string-typed UI form state
//   WorkingHoursDayInput  - per-day editor row (closed/open/close)
//   ErrorMap              - Record<string, string> with dotted keys
//   parseTime             - 'HH:MM' → minutes since midnight (-1 invalid)
//   validateCoords        - lat/lon range checks
//   validateDelivery      - radius/min/free/fee checks + cross-field rule
//   validateLoyalty       - 0..100 percent integer check
//   validateTiming        - prep/delivery/auto-close minute checks
//   validateWorkingHours  - per-day open<close + format checks
//   validateAll           - merge of all validators
//   isFormValid           - convenience boolean wrapper
//   responseToForm        - ShopSettingsResponse → SettingsFormState (kopecks→rubles)
//   formToPayload         - SettingsFormState → ShopSettingsUpdate (rubles→kopecks)
// END_MODULE_MAP

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

// START_CONTRACT: parseTime
//   PURPOSE: Parse an 'HH:MM' string into minutes since midnight.
//   INPUTS:  s: string
//   OUTPUTS: number — minutes [0, 1440); -1 if format invalid or out of range.
//   SIDE_EFFECTS: none.
// END_CONTRACT: parseTime
// 'HH:MM' → число минут с полуночи. -1 если невалидный формат.
export function parseTime(s: string): number {
  const m = /^(\d{2}):(\d{2})$/.exec(s);
  if (!m) return -1;
  const hh = Number(m[1]);
  const mm = Number(m[2]);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return -1;
  return hh * 60 + mm;
}

// START_CONTRACT: validateCoords
//   PURPOSE: Validate shop_lat/shop_lon are finite and within geographic ranges.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap — keys: 'shop_lat', 'shop_lon'.
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateCoords
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

// START_CONTRACT: validateDelivery
//   PURPOSE: Validate radius/min/free/fee fields and the cross-field rule that
//            free_delivery_threshold ≥ min_delivery_amount.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateDelivery
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

// START_CONTRACT: validateLoyalty
//   PURPOSE: Validate loyalty_percent is an integer in [0, 100].
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateLoyalty
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

// START_CONTRACT: validateTiming
//   PURPOSE: Validate prep/delivery/auto-close fields are positive integers
//            (auto-close additionally capped at 1440 minutes).
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateTiming
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

// START_CONTRACT: validateWorkingHours
//   PURPOSE: Validate every non-closed day has well-formed times and open<close.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap — dotted keys 'working_hours.<day>.open'/'.close'.
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateWorkingHours
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

// START_CONTRACT: validateAll
//   PURPOSE: Aggregate every validator into a single ErrorMap.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ErrorMap
//   SIDE_EFFECTS: none.
// END_CONTRACT: validateAll
export function validateAll(form: SettingsFormState): ErrorMap {
  return {
    ...validateCoords(form),
    ...validateDelivery(form),
    ...validateLoyalty(form),
    ...validateTiming(form),
    ...validateWorkingHours(form),
  };
}

// START_CONTRACT: isFormValid
//   PURPOSE: Convenience wrapper — true iff validateAll returned no errors.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: boolean
//   SIDE_EFFECTS: none.
// END_CONTRACT: isFormValid
export function isFormValid(form: SettingsFormState): boolean {
  return Object.keys(validateAll(form)).length === 0;
}

// ── Initial ↔ form mapping ───────────────────────────────────────────────────

import type { ShopSettingsResponse, ShopSettingsUpdate } from '@/api/admin-settings';
import { kopecksToRubles, toKopecks } from '@/api/admin-settings';

// START_CONTRACT: responseToForm
//   PURPOSE: Convert a ShopSettingsResponse from the server (kopecks for money,
//            null-or-day for working_hours) into the string-typed UI form.
//   INPUTS:  r: ShopSettingsResponse
//   OUTPUTS: SettingsFormState
//   SIDE_EFFECTS: none.
// END_CONTRACT: responseToForm
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

// START_CONTRACT: formToPayload
//   PURPOSE: Convert the UI form back to the wire shape expected by PUT
//            /api/v1/admin/settings — Number()-coerce strings, kopecks for money,
//            null for closed days.
//   INPUTS:  form: SettingsFormState
//   OUTPUTS: ShopSettingsUpdate
//   SIDE_EFFECTS: none.
// END_CONTRACT: formToPayload
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
