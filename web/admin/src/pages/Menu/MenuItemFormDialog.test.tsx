import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import '@/i18n/config';
import { MenuItemFormDialog } from './MenuItemFormDialog';

vi.mock('@/api/menu', () => ({
  createItem: vi.fn().mockResolvedValue({
    id: 1,
    category_id: 1,
    name_ru: 'Латте',
    name_en: 'Latte',
    description_ru: null,
    description_en: null,
    base_price: 35000,
    image_url: null,
    media_type: null,
    media_url: null,
    media_poster_url: null,
    available: true,
    archived: false,
    availability: 'available',
    sort_order: 0,
    size_options: [],
    modifiers: [],
  }),
  updateItem: vi.fn(),
  createSize: vi.fn(),
  updateSize: vi.fn(),
  deleteSize: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(status: number, message: string, body?: unknown) {
      super(message);
      this.status = status;
      this.body = body;
    }
  },
}));

const mockCategories = [
  {
    id: 1,
    type: 'drink' as const,
    name_ru: 'Кофе',
    name_en: 'Coffee',
    sort_order: 0,
    is_visible: true,
  },
];

describe('MenuItemFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('MenuItemFormDialog has bilingual, price, sort, legacy image, and media fields', () => {
    render(
      <MenuItemFormDialog
        open={true}
        onClose={vi.fn()}
        categories={mockCategories}
        modifiers={[]}
        item={null}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Name (RU)')).toBeInTheDocument();
    expect(screen.getByLabelText('Name (EN)')).toBeInTheDocument();
    expect(screen.getByLabelText('Description (RU)')).toBeInTheDocument();
    expect(screen.getByLabelText('Description (EN)')).toBeInTheDocument();
    expect(screen.getByLabelText('Sort Order')).toBeInTheDocument();
    expect(screen.getByLabelText('Image URL')).toBeInTheDocument();
    expect(screen.getByLabelText('Media type')).toBeInTheDocument();
    expect(screen.getByLabelText('Media path')).toBeDisabled();
  });

  test('MenuItemFormDialog submits bilingual payload with base_price', async () => {
    const { createItem } = await import('@/api/menu');

    render(
      <MenuItemFormDialog
        open={true}
        onClose={vi.fn()}
        categories={mockCategories}
        modifiers={[]}
        item={null}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('Name (RU)'), {
      target: { value: 'Латте' },
    });
    fireEvent.change(screen.getByLabelText('Name (EN)'), {
      target: { value: 'Latte' },
    });
    fireEvent.change(screen.getByLabelText('Price (₽)'), {
      target: { value: '350' },
    });

    // Выбираем категорию (первый вариант — "Coffee")
    const catSelect = screen.getByRole('combobox', { name: /category/i });
    fireEvent.change(catSelect, { target: { value: '1' } });

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => {
      expect(createItem).toHaveBeenCalledWith(
        expect.objectContaining({
          name_ru: 'Латте',
          name_en: 'Latte',
          base_price: 35000,
          category_id: 1,
        }),
      );
    });

    // Проверяем отсутствие старых полей
    const call = (createItem as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call).not.toHaveProperty('name');
    expect(call).not.toHaveProperty('price_kopecks');
  });

  test('MenuItemFormDialog submits video media payload with poster path', async () => {
    const { createItem } = await import('@/api/menu');

    render(
      <MenuItemFormDialog
        open={true}
        onClose={vi.fn()}
        categories={mockCategories}
        modifiers={[]}
        item={null}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('Name (RU)'), {
      target: { value: 'Латте' },
    });
    fireEvent.change(screen.getByLabelText('Name (EN)'), {
      target: { value: 'Latte' },
    });
    fireEvent.change(screen.getByLabelText('Price (₽)'), {
      target: { value: '350' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /category/i }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /media type/i }), {
      target: { value: 'video' },
    });
    fireEvent.change(screen.getByLabelText('Video path'), {
      target: { value: '/media/menu/latte/hero.mp4' },
    });
    fireEvent.change(screen.getByLabelText('Poster path'), {
      target: { value: '/media/menu/latte/poster.webp' },
    });

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => {
      expect(createItem).toHaveBeenCalledWith(
        expect.objectContaining({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        }),
      );
    });
  });

  test('MenuItemFormDialog requires poster path for video media', async () => {
    const { createItem } = await import('@/api/menu');

    render(
      <MenuItemFormDialog
        open={true}
        onClose={vi.fn()}
        categories={mockCategories}
        modifiers={[]}
        item={null}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('Name (RU)'), {
      target: { value: 'Латте' },
    });
    fireEvent.change(screen.getByLabelText('Name (EN)'), {
      target: { value: 'Latte' },
    });
    fireEvent.change(screen.getByLabelText('Price (₽)'), {
      target: { value: '350' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /category/i }), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /media type/i }), {
      target: { value: 'video' },
    });
    fireEvent.change(screen.getByLabelText('Video path'), {
      target: { value: '/media/menu/latte/hero.mp4' },
    });

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));

    expect(
      await screen.findByText('Poster path is required for video'),
    ).toBeInTheDocument();
    expect(createItem).not.toHaveBeenCalled();
  });
});
