// Клиент эндпоинта GET /api/v1/admin/stats (PDD §4.5, §7.1 Phase 6 item 1).
// Shape совпадает с AdminStatsResponse из dashboard-api (services/core-api
// schemas/admin_stats.py).

import { authenticatedFetch, ApiError } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Typed client for admin dashboard stats endpoint — revenue, orders
//            count, popular items per range (today/week/month).
//   SCOPE:   Wraps GET /api/v1/admin/stats; mirrors AdminStatsResponse from
//            services/core-api schemas/admin_stats.py.
//   DEPENDS: ./client.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §4.5/§7.1 phase 6 dashboard,
//            INV-002 (admin-only endpoint), INV-014 (popular_items use snapshot
//            name fields so historical orders stay stable even if menu items rename).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ApiError              - re-export
//   StatsRange            - 'today' | 'week' | 'month'
//   PopularItem           - one row in popular items list
//   AdminStatsResponse    - response shape
//   getAdminStats         - GET /api/v1/admin/stats?range=
// END_MODULE_MAP

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

// START_CONTRACT: getAdminStats
//   PURPOSE: Fetch dashboard stats for a given range (admin only).
//   INPUTS:  range: StatsRange
//   OUTPUTS: Promise<AdminStatsResponse>
//   SIDE_EFFECTS: GET; 401 redirects via authenticatedFetch.
//   LINKS:   INV-002, INV-014.
// END_CONTRACT: getAdminStats
export const getAdminStats = (range: StatsRange): Promise<AdminStatsResponse> =>
  json(`/api/v1/admin/stats?range=${encodeURIComponent(range)}`);
