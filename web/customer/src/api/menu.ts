import { apiRequest } from './client';
import type { PublicMenuResponse } from './menuTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Public menu REST client — GET /api/v1/menu with Accept-Language so
//            the server pre-resolves localized name/description fields.
//   SCOPE:   fetchPublicMenu (the only public function; types come from menuTypes).
//   DEPENDS: M-CORE-API (HTTP /api/v1/menu), ./client (apiRequest), ./menuTypes.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §3 menu.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   fetchPublicMenu  - GET /api/v1/menu localized to ru|en, returns PublicMenuResponse
// END_MODULE_MAP

// START_CONTRACT: fetchPublicMenu
//   PURPOSE: Load the menu (categories + items + sizes + modifiers) localized
//            to the given language.
//   INPUTS:  language: 'ru' | 'en' — sent as Accept-Language header.
//   OUTPUTS: Promise<PublicMenuResponse> — { categories: PublicCategory[] }.
//   SIDE_EFFECTS: HTTP GET /api/v1/menu; throws ApiError on non-2xx.
//   LINKS:   PDD §3 menu; MenuPage subscribes to language change events to refetch.
// END_CONTRACT: fetchPublicMenu
export function fetchPublicMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse> {
  return apiRequest<PublicMenuResponse>('/api/v1/menu', {
    headers: { 'Accept-Language': language },
  });
}
