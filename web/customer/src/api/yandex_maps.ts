import { authenticatedFetch } from './client';

// START_MODULE_CONTRACT
//   PURPOSE: Yandex.Maps REST client — talks to the core-api proxy
//            /api/v1/maps/* (the real Yandex API key is never exposed to the
//            browser, see AGENTS.md "must not"). Wraps suggest + geocode
//            calls and maps 503/network failures into MapsUnavailableError so
//            AddressAutocomplete can drop into degraded plain-text mode.
//            Suggest accepts the current backend bare-array response and the
//            older {items: [...]} wrapper for compatibility.
//   SCOPE:   MapsLang, SuggestResult, GeocodeResult types, MapsUnavailableError,
//            suggest, geocode.
//   DEPENDS: M-CORE-API (HTTP /api/v1/maps/*), ./client (authenticatedFetch).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §7.3 / §8.3 maps
//            degradation. INV-013 — query strings can be PII; UI must not log
//            verbatim queries.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MapsLang                - 'ru_RU' | 'en_US' query-string locale
//   SuggestResult           - one address suggestion (text + optional coords)
//   GeocodeResult           - canonical address resolution result
//   MapsUnavailableError    - thrown on 503/network so caller degrades gracefully
//   suggest                 - GET /maps/suggest — autocomplete suggestions
//   geocode                 - GET /maps/geocode — resolve text to coords
// END_MODULE_MAP

export type MapsLang = 'ru_RU' | 'en_US';

export interface SuggestResult {
  text: string;
  lat: number | null;
  lon: number | null;
  precision?: string;
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  precision: string;
  canonical_text: string;
}

// START_CONTRACT: MapsUnavailableError
//   PURPOSE: Marker error class for "Yandex.Maps proxy is unavailable" (503,
//            timeout, network, 5xx). AddressAutocomplete catches this and
//            switches to degraded plain-text input for the rest of the mount
//            session.
//   INPUTS:  message?: string — defaults to 'Maps API unavailable'.
//   OUTPUTS: MapsUnavailableError instance.
//   SIDE_EFFECTS: none.
//   LINKS:   PDD §8.3 degraded address input.
// END_CONTRACT: MapsUnavailableError
// Маркер недоступности Яндекс.Карт: 503, timeout, network error.
// Компонент автокомплита ловит её и уходит в degraded-режим (§8.3).
export class MapsUnavailableError extends Error {
  constructor(message = 'Maps API unavailable') {
    super(message);
    this.name = 'MapsUnavailableError';
  }
}

// START_CONTRACT: suggest
//   PURPOSE: Fetch address autocomplete suggestions from the core-api Yandex.Maps
//            proxy.
//   INPUTS:  query: string  — partial address string (INV-013 PII; do not log)
//            lang: MapsLang — 'ru_RU' | 'en_US' for language hint.
//   OUTPUTS: Promise<SuggestResult[]> — possibly empty array.
//   SIDE_EFFECTS: HTTP GET /api/v1/maps/suggest. Throws MapsUnavailableError on
//                 5xx / network failure; throws plain Error on other non-2xx.
//   LINKS:   PDD §8.3; AddressAutocomplete is the only caller.
// END_CONTRACT: suggest
export async function suggest(
  query: string,
  lang: MapsLang,
): Promise<SuggestResult[]> {
  const url = `/api/v1/maps/suggest?text=${encodeURIComponent(query)}&lang=${lang}`;
  let res: Response;
  try {
    res = await authenticatedFetch(url);
  } catch {
    throw new MapsUnavailableError();
  }
  if (res.status >= 500) {
    throw new MapsUnavailableError();
  }
  if (!res.ok) {
    throw new Error(`Suggest failed: HTTP ${res.status}`);
  }
  const body = (await res.json()) as unknown;
  if (Array.isArray(body)) {
    return body as SuggestResult[];
  }
  if (
    body &&
    typeof body === 'object' &&
    Array.isArray((body as { items?: unknown }).items)
  ) {
    return (body as { items: SuggestResult[] }).items;
  }
  return [];
}

// START_CONTRACT: geocode
//   PURPOSE: Resolve a free-text address to canonical text + coordinates.
//   INPUTS:  text: string — full address (INV-013 PII)
//            lang?: MapsLang — defaults to 'ru_RU'
//   OUTPUTS: Promise<GeocodeResult | null> — null when server returns 404
//            (address not found).
//   SIDE_EFFECTS: HTTP GET /api/v1/maps/geocode; throws MapsUnavailableError on
//                 5xx / network; plain Error on other non-2xx.
//   LINKS:   PDD §8.3 geocode fallback.
// END_CONTRACT: geocode
export async function geocode(
  text: string,
  lang: MapsLang = 'ru_RU',
): Promise<GeocodeResult | null> {
  const url = `/api/v1/maps/geocode?text=${encodeURIComponent(text)}&lang=${lang}`;
  let res: Response;
  try {
    res = await authenticatedFetch(url);
  } catch {
    throw new MapsUnavailableError();
  }
  if (res.status >= 500) {
    throw new MapsUnavailableError();
  }
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Geocode failed: HTTP ${res.status}`);
  }
  return (await res.json()) as GeocodeResult;
}
