import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));

import { CartLine } from './CartLine';
import type { CartItemResponse } from '@/api/cartTypes';

function makeItem(overrides: Partial<CartItemResponse> = {}): CartItemResponse {
  return {
    line_id: 'line-1',
    menu_item_id: 1,
    size_option_id: null,
    modifier_ids: [],
    quantity: 2,
    unit_price: 20000,
    line_total: 40000,
    menu_item_snapshot: { name_ru: 'Лате', name_en: 'Latte', availability: 'available' },
    size_snapshot: null,
    modifiers_snapshot: [],
    ...overrides,
  };
}

describe('CartLine', () => {
  it('renders name, line total, and unit price', () => {
    render(
      <CartLine
        item={makeItem()}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.getByText('Лате')).toBeDefined();
    expect(screen.getAllByText(/200/).length).toBeGreaterThan(0); // 200 ₽ unit
    expect(screen.getAllByText(/400/).length).toBeGreaterThan(0); // 400 ₽ line total
  });

  it('renders size label when present', () => {
    render(
      <CartLine
        item={makeItem({ size_snapshot: { label: 'L', price: 20000 } })}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.getByText('L')).toBeDefined();
  });

  it('renders two modifiers joined by separator', () => {
    render(
      <CartLine
        item={makeItem({
          modifiers_snapshot: [
            { id: 1, name_ru: 'Сироп', name_en: 'Syrup', price: 5000 },
            { id: 2, name_ru: 'Молоко', name_en: 'Milk', price: 3000 },
          ],
        })}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.getByText(/Сироп.*Молоко|Молоко.*Сироп/)).toBeDefined();
  });

  it('decrement at quantity 1 calls onRemove instead of onUpdateQuantity', () => {
    const onRemove = vi.fn();
    const onUpdate = vi.fn();
    render(
      <CartLine
        item={makeItem({ quantity: 1, line_total: 20000 })}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={onUpdate}
        onRemove={onRemove}
      />,
    );

    const dec = screen.getByRole('button', { name: 'cart.decrement' }) as HTMLButtonElement;
    expect(dec.disabled).toBe(false);
    fireEvent.click(dec);
    expect(onRemove).toHaveBeenCalledOnce();
    expect(onRemove).toHaveBeenCalledWith('item-1');
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('increment button is disabled at quantity 99', () => {
    render(
      <CartLine
        item={makeItem({ quantity: 99, line_total: 1980000 })}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    const inc = screen.getByRole('button', { name: 'cart.increment' }) as HTMLButtonElement;
    expect(inc.disabled).toBe(true);
  });

  it('clicking + at quantity 1 calls onUpdateQuantity with 2', () => {
    const onUpdate = vi.fn();
    render(
      <CartLine
        item={makeItem({ quantity: 1, line_total: 20000 })}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={onUpdate}
        onRemove={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'cart.increment' }));
    expect(onUpdate).toHaveBeenCalledOnce();
    expect(onUpdate).toHaveBeenCalledWith('item-1', 2);
  });

  it('clicking remove calls onRemove with itemId once', () => {
    const onRemove = vi.fn();
    render(
      <CartLine
        item={makeItem()}
        lang="ru"
        itemId="item-1"
        onUpdateQuantity={vi.fn()}
        onRemove={onRemove}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'cart.remove' }));
    expect(onRemove).toHaveBeenCalledOnce();
    expect(onRemove).toHaveBeenCalledWith('item-1');
  });
});
