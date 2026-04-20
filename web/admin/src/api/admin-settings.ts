// Типы зеркалят Pydantic-схемы из
// services/core-api/src/core_api/schemas/shop_settings.py.
// Runtime-валидация — серверная, клиент делает UX-подсказки.

import { authenticatedFetch, ApiError } from './client';

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

export function toKopecks(rubles: number): number {
  return Math.round(rubles * 100);
}

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

export const getSettings = (): Promise<ShopSettingsResponse> =>
  json('/api/v1/admin/settings');

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
