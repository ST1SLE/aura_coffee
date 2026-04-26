// Типы зеркалят Pydantic-схемы из
// services/core-api/src/core_api/schemas/shop_settings.py.
// Runtime-валидация — серверная, клиент делает UX-подсказки.

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin shop settings — working hours, delivery
//            radius/fees, loyalty percent, timing thresholds — plus rubles<>kopecks
//            converters and FastAPI 422 deep-error parser.
//   SCOPE:   Wraps GET/PUT /api/v1/admin/settings (admin only). UI works in
//            rubles, wire format is kopecks.
//   DEPENDS: ./client (authenticatedFetch, ApiError).
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §6.6 shop settings,
//            INV-002 (admin scope enforced server-side).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError              - re-export from ./client
//   DayKey                - 'mon'|'tue'|...|'sun'
//   DAYS                  - readonly DayKey[] in week order
//   WorkingHoursDay       - {open, close} 'HH:MM' pair
//   WorkingHours          - Record<DayKey, WorkingHoursDay | null>
//   ShopSettingsResponse  - GET response shape
//   ShopSettingsUpdate    - PUT body shape (kopecks)
//   toKopecks             - rubles number → integer kopecks
//   kopecksToRubles       - kopecks → rubles string for UI inputs
//   getSettings           - GET /api/v1/admin/settings
//   updateSettings        - PUT /api/v1/admin/settings
//   parseFieldErrorsDeep  - FastAPI 422 deep-path → flat error map
// END_MODULE_MAP

export { ApiError };

// ── Working hours ────────────────────────────────────────────────────────────

export type DayKey = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

export const DAYS: readonly DayKey[] = [
  'mon',
  'tue',
  'wed',
  'thu',
  'fri',
  'sat',
  'sun',
];

export interface WorkingHoursDay {
  open: string; // "HH:MM"
  close: string; // "HH:MM"
}

export type WorkingHours = Record<DayKey, WorkingHoursDay | null>;

// ── Response / Update shapes ─────────────────────────────────────────────────

export interface ShopSettingsResponse {
  shop_lat: number;
  shop_lon: number;
  delivery_radius_km: number;
  min_delivery_amount: number;
  free_delivery_threshold: number;
  delivery_fee: number;
  loyalty_percent: number;
  default_prep_time_minutes: number;
  estimated_delivery_time_minutes: number;
  auto_close_minutes: number;
  working_hours: WorkingHours;
  updated_at: string;
}

export interface ShopSettingsUpdate {
  shop_lat: number;
  shop_lon: number;
  delivery_radius_km: number;
  min_delivery_amount: number; // копейки
  free_delivery_threshold: number; // копейки
  delivery_fee: number; // копейки
  loyalty_percent: number;
  default_prep_time_minutes: number;
  estimated_delivery_time_minutes: number;
  auto_close_minutes: number;
  working_hours: WorkingHours;
}

// ── Money helpers (UI работает с рублями, API — с копейками) ─────────────────

// START_CONTRACT: toKopecks
//   PURPOSE: Convert rubles (UI) to integer kopecks (wire) — Math.round to
//            absorb floating-point drift.
//   INPUTS:  rubles: number
//   OUTPUTS: number — integer kopecks
//   SIDE_EFFECTS: none.
// END_CONTRACT: toKopecks
export function toKopecks(rubles: number): number {
  return Math.round(rubles * 100);
}

// START_CONTRACT: kopecksToRubles
//   PURPOSE: Convert kopecks (wire) to a compact rubles string for UI inputs;
//            strips trailing ".00" and a single trailing zero in tenths.
//   INPUTS:  kopecks: number
//   OUTPUTS: string
//   SIDE_EFFECTS: none.
// END_CONTRACT: kopecksToRubles
export function kopecksToRubles(kopecks: number): string {
  const rubles = kopecks / 100;
  const rounded = Math.round(rubles * 100) / 100;
  const s = rounded.toFixed(2);
  return s.replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
}

// ── API functions ────────────────────────────────────────────────────────────

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// START_CONTRACT: getSettings
//   PURPOSE: Fetch current shop settings (admin only).
//   INPUTS:  none
//   OUTPUTS: Promise<ShopSettingsResponse>
//   SIDE_EFFECTS: GET; 401/403.
//   LINKS:   INV-002.
// END_CONTRACT: getSettings
export const getSettings = (): Promise<ShopSettingsResponse> =>
  json('/api/v1/admin/settings');

// START_CONTRACT: updateSettings
//   PURPOSE: Replace the full shop settings document (admin only).
//   INPUTS:  payload: ShopSettingsUpdate (kopecks for money fields)
//   OUTPUTS: Promise<ShopSettingsResponse>
//   SIDE_EFFECTS: PUT; 422 on validation, 401/403 on auth.
//   LINKS:   INV-002.
// END_CONTRACT: updateSettings
export const updateSettings = (
  payload: ShopSettingsUpdate,
): Promise<ShopSettingsResponse> =>
  json('/api/v1/admin/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

// ── 422 error parsing ────────────────────────────────────────────────────────

// FastAPI 422: detail = [{ loc: ['body', '<field>', ...], msg: '...' }, ...].
// Возвращаем flat-объект { 'field.path': 'msg' } — префикс 'body' отрезаем,
// остальное join'им через '.'. Для 'working_hours.mon.open' путь —
// ['body', 'working_hours', 'mon', 'open'] → 'working_hours.mon.open'.

// START_CONTRACT: parseFieldErrorsDeep
//   PURPOSE: Convert a FastAPI 422 ApiError into a flat {dotted.path: msg} map
//            so deeply-nested validation errors (e.g. working_hours.mon.open)
//            can be surfaced under the correct field in the form.
//   INPUTS:  err: unknown — caller passes the rejection value as-is.
//   OUTPUTS: Record<string, string> — empty if not an ApiError or no detail.
//   SIDE_EFFECTS: none.
// END_CONTRACT: parseFieldErrorsDeep
export function parseFieldErrorsDeep(err: unknown): Record<string, string> {
  if (!(err instanceof ApiError)) return {};
  const body = err.body as
    | { detail?: Array<{ loc?: unknown[]; msg?: string }> }
    | null
    | undefined;
  if (!body?.detail || !Array.isArray(body.detail)) return {};
  const out: Record<string, string> = {};
  for (const d of body.detail) {
    if (!Array.isArray(d.loc) || typeof d.msg !== 'string') continue;
    const parts = d.loc
      .filter((p) => typeof p === 'string' || typeof p === 'number')
      .map((p) => String(p));
    if (parts.length > 0 && parts[0] === 'body') parts.shift();
    if (parts.length === 0) continue;
    const key = parts.join('.');
    if (!(key in out)) out[key] = d.msg;
  }
  return out;
}
