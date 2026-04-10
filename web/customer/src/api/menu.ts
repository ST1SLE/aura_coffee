import { apiRequest } from './client';
import type { PublicMenuResponse } from './menuTypes';

export function fetchPublicMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse> {
  return apiRequest<PublicMenuResponse>('/api/v1/menu', {
    headers: { 'Accept-Language': language },
  });
}
