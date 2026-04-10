import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));

import { MenuItemCard } from './MenuItemCard';
import type { PublicMenuItem } from '@/api/menuTypes';

function makeItem(overrides: Partial<PublicMenuItem> = {}): PublicMenuItem {
  return {
    id: 1, category_id: 1,
    name: 'Лате', name_ru: 'Лате', name_en: 'Latte',
    description: null, description_ru: null, description_en: null,
    base_price: 25000, image_url: null, available: true, sort_order: 0,
    size_options: [], modifiers: [],
    ...overrides,
  };
}

describe('MenuItemCard', () => {
  it('renders item.name verbatim', () => {
    render(<MenuItemCard item={makeItem({ name: 'Капучино' })} lang="ru" onOpen={vi.fn()} />);
    expect(screen.getByText('Капучино')).toBeDefined();
  });

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
});
