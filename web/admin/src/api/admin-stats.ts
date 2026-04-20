// Клиент эндпоинта GET /api/v1/admin/stats (PDD §4.5, §7.1 Phase 6 item 1).
// Shape совпадает с AdminStatsResponse из dashboard-api (services/core-api
// schemas/admin_stats.py).

import { authenticatedFetch, ApiError } from './client';

export { ApiError };

export type StatsRange = 'today' | 'week' | 'month';

export interface PopularItem {
  name_ru: string;
  name_en: string;
  quantity: number;
}

export interface AdminStatsResponse {
  range: StatsRange;
  range_start: string;
  range_end: string;
  revenue_kopecks: number;
  orders_count: number;
  popular_items: PopularItem[];
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(path, init);
  return res.json() as Promise<T>;
}

export const getAdminStats = (range: StatsRange): Promise<AdminStatsResponse> =>
  json(`/api/v1/admin/stats?range=${encodeURIComponent(range)}`);
