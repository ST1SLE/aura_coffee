import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { MenuItemsTable } from './MenuItemsTable';
import * as menuApi from '@/api/menu';

const mockItem = {
  id: 1,
  category_id: 1,
  name_ru: 'Кофе',
  name_en: 'Coffee',
  description_ru: null,
  description_en: null,
  base_price: 35000,
  image_url: null,
  media_type: null,
  media_url: null,
  media_poster_url: null,
  inventory_quantity: 4,
  available: true,
  archived: false,
  availability: 'available' as const,
  sort_order: 0,
  size_options: [],
  modifiers: [],
};

vi.mock('@/api/menu', () => ({
  listItems: vi.fn().mockResolvedValue([]),
  deleteItem: vi.fn(),
  setItemAvailability: vi.fn(),
  setItemInventory: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

describe('MenuItemsTable', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.mocked(menuApi.listItems).mockResolvedValue([mockItem]);
    await i18n.changeLanguage('en');
  });

  test('MenuItemsTable renders picked name and base_price', async () => {
    render(
      <MenuItemsTable
        categoryId={null}
        categories={[]}
        modifiers={[]}
        currentRole="admin"
        onError={vi.fn()}
      />,
    );

    // Ждём подгрузки данных (en locale по умолчанию — отображается name_en)
    const nameCell = await screen.findByText('Coffee');
    expect(nameCell).toBeInTheDocument();

    // Цена содержит 350 (35000 копеек = 350 рублей)
    const rows = screen.getAllByRole('row');
    const rowText = rows[1]?.textContent ?? '';
    expect(rowText).toContain('350');
    expect(rowText).toContain('Finite: 4');
  });

  test('MenuItemsTable lets barista update finite inventory through operational endpoint', async () => {
    vi.mocked(menuApi.setItemInventory).mockResolvedValue({
      ...mockItem,
      inventory_quantity: 7,
    });

    render(
      <MenuItemsTable
        categoryId={null}
        categories={[]}
        modifiers={[]}
        currentRole="barista"
        onError={vi.fn()}
      />,
    );

    const inventoryInput = await screen.findByLabelText(
      'Inventory quantity for Coffee',
    );
    fireEvent.change(inventoryInput, { target: { value: '7' } });
    fireEvent.click(
      screen.getByRole('button', { name: 'Save inventory for Coffee' }),
    );

    await waitFor(() => {
      expect(menuApi.setItemInventory).toHaveBeenCalledWith(1, 7);
    });
  });

  test('MenuItemsTable renders unlimited and out-of-stock inventory labels', async () => {
    vi.mocked(menuApi.listItems).mockResolvedValue([
      { ...mockItem, id: 1, name_en: 'Coffee', inventory_quantity: null },
      { ...mockItem, id: 2, name_en: 'Tea', inventory_quantity: 0 },
    ]);

    render(
      <MenuItemsTable
        categoryId={null}
        categories={[]}
        modifiers={[]}
        currentRole="admin"
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByText('Unlimited')).toBeInTheDocument();
    expect(await screen.findByText('Out of stock')).toBeInTheDocument();
  });
});
