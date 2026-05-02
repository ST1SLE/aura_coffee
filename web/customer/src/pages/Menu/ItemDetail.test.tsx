import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));
vi.mock('@/store/cart', () => ({
  useCartStore: vi.fn(),
}));

import { useCartStore } from '@/store/cart';
import { ItemDetail } from './ItemDetail';
import type { PublicMenuItem } from '@/api/menuTypes';

function baseItem(overrides: Partial<PublicMenuItem> = {}): PublicMenuItem {
  return {
    id: 1,
    category_id: 1,
    name: 'Кофе',
    name_ru: 'Кофе',
    name_en: 'Coffee',
    description: null,
    description_ru: null,
    description_en: null,
    base_price: 15000,
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

beforeEach(() => {
  vi.clearAllMocks();
  (useCartStore as unknown as Mock).mockReturnValue(
    vi.fn().mockResolvedValue(undefined),
  );
});

describe('ItemDetail — price display', () => {
  it('selecting size L (price 22000) shows 220 ₽', () => {
    const item = baseItem({
      size_options: [
        { id: 1, label: 'S', price: 15000, available: true },
        { id: 2, label: 'L', price: 22000, available: true },
      ],
    });
    render(<ItemDetail item={item} lang="ru" onClose={vi.fn()} />);

    // Выбираем размер L
    fireEvent.click(screen.getByRole('button', { name: /L/ }));

    expect(screen.getAllByText(/220/).length).toBeGreaterThan(0);
  });

  it('adding a modifier (price 5000) on top of size (15000) shows 200 ₽', () => {
    const item = baseItem({
      size_options: [{ id: 1, label: 'M', price: 15000, available: true }],
      modifiers: [
        {
          id: 10,
          name: 'Сироп',
          name_ru: 'Сироп',
          name_en: 'Syrup',
          price: 5000,
          available: true,
        },
      ],
    });
    render(<ItemDetail item={item} lang="ru" onClose={vi.fn()} />);

    // Размер M уже выбран (первый по умолчанию), добавляем модификатор
    fireEvent.click(screen.getByRole('button', { name: /Сироп/ }));

    expect(screen.getAllByText(/200/).length).toBeGreaterThan(0);
  });
});

describe('ItemDetail — unavailable options', () => {
  it('unavailable size option renders as disabled', () => {
    const item = baseItem({
      size_options: [
        { id: 1, label: 'S', price: 10000, available: false },
        { id: 2, label: 'L', price: 20000, available: true },
      ],
    });
    render(<ItemDetail item={item} lang="ru" onClose={vi.fn()} />);

    const sBtn = screen.getByRole('button', { name: /S/ });
    expect(sBtn).toBeDefined();
    expect((sBtn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('ItemDetail — Add-to-Cart guard', () => {
  it('Add-to-Cart button disabled when no size selected among multiple sizes', () => {
    // Создаём item без доступных размеров (все недоступны) → selectedSize будет null
    const item = baseItem({
      size_options: [
        { id: 1, label: 'S', price: 10000, available: false },
        { id: 2, label: 'L', price: 20000, available: false },
      ],
    });
    render(<ItemDetail item={item} lang="ru" onClose={vi.fn()} />);

    const addBtn = screen.getByRole('button', { name: 'menu.addToCart' });
    expect((addBtn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('ItemDetail — Add-to-Cart actions (task 6.8)', () => {
  it('success: closes the view and calls the store with selected payload', async () => {
    const addItem = vi.fn().mockResolvedValue(undefined);
    (useCartStore as unknown as Mock).mockReturnValue(addItem);

    const onClose = vi.fn();
    const item = baseItem({
      modifiers: [
        {
          id: 5,
          name: 'Экстра',
          name_ru: 'Экстра',
          name_en: 'Extra',
          price: 3000,
          available: true,
        },
      ],
    });
    render(<ItemDetail item={item} lang="ru" onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: /Экстра/ }));
    fireEvent.click(screen.getByRole('button', { name: 'menu.addToCart' }));

    await waitFor(() => {
      expect(addItem).toHaveBeenCalledWith({
        menu_item_id: 1,
        size_option_id: null,
        modifier_ids: [5],
        quantity: 1,
      });
    });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('finite stock quantity stepper caps the add payload', async () => {
    const addItem = vi.fn().mockResolvedValue(undefined);
    (useCartStore as unknown as Mock).mockReturnValue(addItem);

    render(
      <ItemDetail
        item={baseItem({ inventory_quantity: 2 })}
        lang="ru"
        onClose={vi.fn()}
      />,
    );

    const inc = screen.getByRole('button', { name: 'cart.increment' });
    fireEvent.click(inc);
    expect((inc as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: 'menu.addToCart' }));

    await waitFor(() => {
      expect(addItem).toHaveBeenCalledWith({
        menu_item_id: 1,
        size_option_id: null,
        modifier_ids: [],
        quantity: 2,
      });
    });
  });

  it('sold-out finite stock disables add-to-cart', () => {
    render(
      <ItemDetail
        item={baseItem({ inventory_quantity: 0 })}
        lang="ru"
        onClose={vi.fn()}
      />,
    );

    const addBtn = screen.getByRole('button', { name: 'menu.addToCart' });
    expect((addBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('menu.soldOut')).toBeDefined();
  });

  it('failure: keeps view open and shows error toast', async () => {
    const addItem = vi.fn().mockRejectedValue(new Error('HTTP 409'));
    (useCartStore as unknown as Mock).mockReturnValue(addItem);

    const onClose = vi.fn();
    render(<ItemDetail item={baseItem()} lang="ru" onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'menu.addToCart' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toBeDefined();
    });

    expect(onClose).not.toHaveBeenCalled();
  });
});
