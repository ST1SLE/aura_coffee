import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));

import { MenuItemCard } from './MenuItemCard';
import type { MenuItemResponse } from '@/api/menuTypes';

function makeItem(overrides: Partial<MenuItemResponse> = {}): MenuItemResponse {
  return {
    id: 1, category_id: 1, name_ru: 'Лате', name_en: 'Latte',
    description_ru: null, description_en: null, base_price: 25000,
    image_url: null, available: true, archived: false, sort_order: 0,
    created_at: null, updated_at: null, size_options: [], modifiers: [],
    availability: 'available',
    ...overrides,
  };
}

describe('MenuItemCard', () => {
  it('clicking available card fires onOpen once', () => {
    const onOpen = vi.fn();
    render(<MenuItemCard item={makeItem()} lang="ru" onOpen={onOpen} />);

    fireEvent.click(screen.getByRole('button'));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('clicking unavailable card (available=false) does not fire onOpen', () => {
    const onOpen = vi.fn();
    render(<MenuItemCard item={makeItem({ available: false })} lang="ru" onOpen={onOpen} />);

    fireEvent.click(screen.getByRole('button'));
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('unavailable badge renders for available=false', () => {
    render(<MenuItemCard item={makeItem({ available: false })} lang="ru" onOpen={vi.fn()} />);
    expect(screen.getByText('menu.unavailable')).toBeDefined();
  });

  it('unavailable badge renders for archived=true', () => {
    render(<MenuItemCard item={makeItem({ archived: true })} lang="ru" onOpen={vi.fn()} />);
    expect(screen.getByText('menu.unavailable')).toBeDefined();
  });
});
