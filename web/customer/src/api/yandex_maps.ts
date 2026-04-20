import { authenticatedFetch } from './client';

export type MapsLang = 'ru_RU' | 'en_US';

export interface SuggestResult {
  text: string;
  lat: number;
  lon: number;
}

export interface GeocodeResult {
  text: string;
  lat: number;
  lon: number;
}

// Маркер недоступности Яндекс.Карт: 503, timeout, network error.
// Компонент автокомплита ловит её и уходит в degraded-режим (§8.3).
export class MapsUnavailableError extends Error {
  constructor(message = 'Maps API unavailable') {
    super(message);
    this.name = 'MapsUnavailableError';
  }
}

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
  if (res.status === 503) {
    throw new MapsUnavailableError();
  }
  if (!res.ok) {
    throw new Error(`Suggest failed: HTTP ${res.status}`);
  }
  const body = (await res.json()) as { items?: SuggestResult[] };
  return body.items ?? [];
}

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
  if (res.status === 503) {
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
