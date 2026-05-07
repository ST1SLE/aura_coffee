import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';

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
    id: 1,
    category_id: 1,
    name: 'Лате',
    name_ru: 'Лате',
    name_en: 'Latte',
    description: null,
    description_ru: null,
    description_en: null,
    base_price: 25000,
    image_url: null,
    media_type: null,
    media_url: null,
    media_poster_url: null,
    available: true,
    sort_order: 0,
    size_options: [],
    modifiers: [],
    ...overrides,
  };
}

describe('MenuItemCard', () => {
  beforeEach(() => {
    vi.spyOn(window.HTMLMediaElement.prototype, 'load').mockImplementation(
      () => undefined,
    );
    vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(
      undefined,
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders item.name verbatim', () => {
    render(
      <MenuItemCard
        item={makeItem({ name: 'Капучино' })}
        lang="ru"
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText('Капучино')).toBeDefined();
  });

  it('clicking available card fires onOpen once', () => {
    const onOpen = vi.fn();
    render(<MenuItemCard item={makeItem()} lang="ru" onOpen={onOpen} />);

    const button = screen.getByRole('button') as HTMLButtonElement;
    expect(button.tagName).toBe('BUTTON');
    expect(button.disabled).toBe(false);

    fireEvent.click(button);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('clicking video media opens the available card', () => {
    const onOpen = vi.fn();
    render(
      <MenuItemCard
        item={makeItem({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        })}
        lang="ru"
        onOpen={onOpen}
      />,
    );

    fireEvent.click(screen.getByLabelText('Лате'));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('keeps name and price on the media overlay rather than a separate panel', () => {
    const { container } = render(
      <MenuItemCard
        item={makeItem({ name: 'Раф таро', base_price: 37500 })}
        lang="ru"
        onOpen={vi.fn()}
      />,
    );

    expect(screen.getByText('Раф таро')).toBeDefined();
    expect(screen.getByText(/375/)).toBeDefined();
    expect(
      container.querySelector('.bg-gradient-to-t.from-foreground\\/85'),
    ).toBeDefined();
  });

  it('clicking unavailable card (available=false) does not fire onOpen', () => {
    const onOpen = vi.fn();
    render(
      <MenuItemCard
        item={makeItem({ available: false })}
        lang="ru"
        onOpen={onOpen}
      />,
    );

    const button = screen.getByRole('button') as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    fireEvent.click(button);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('unavailable badge renders for available=false', () => {
    render(
      <MenuItemCard
        item={makeItem({ available: false })}
        lang="ru"
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText('menu.unavailable')).toBeDefined();
  });

  it('sold-out finite stock disables the card and renders sold-out badge', () => {
    const onOpen = vi.fn();
    render(
      <MenuItemCard
        item={makeItem({ inventory_quantity: 0 })}
        lang="ru"
        onOpen={onOpen}
      />,
    );

    const button = screen.getByRole('button') as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    fireEvent.click(button);
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.getByText('menu.soldOut')).toBeDefined();
  });

  it('finite stock count renders when item is available', () => {
    render(
      <MenuItemCard
        item={makeItem({ inventory_quantity: 6 })}
        lang="ru"
        onOpen={vi.fn()}
      />,
    );

    expect(screen.getByText('menu.stockLeft')).toBeDefined();
  });
});
