import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}));
vi.mock('@/api/menu', () => ({
  listCategories: vi.fn(),
  listMenuItems: vi.fn(),
}));
vi.mock('@/store/cart', () => ({
  useCartStore: vi.fn(() => vi.fn()),
}));

import * as menuApi from '@/api/menu';
import { MenuPage } from './MenuPage';
import type { CategoryResponse, MenuItemResponse } from '@/api/menuTypes';

const cat1: CategoryResponse = { id: 1, type: 'drink', name_ru: 'Напитки', name_en: 'Drinks', sort_order: 10, is_visible: true, created_at: null, updated_at: null };
const cat2: CategoryResponse = { id: 2, type: 'food', name_ru: 'Еда', name_en: 'Food', sort_order: 20, is_visible: true, created_at: null, updated_at: null };
const cat3: CategoryResponse = { id: 3, type: 'merch', name_ru: 'Товары', name_en: 'Merch', sort_order: 30, is_visible: true, created_at: null, updated_at: null };

function makeItem(id: number, catId: number, nameRu: string): MenuItemResponse {
  return {
    id, category_id: catId, name_ru: nameRu, name_en: nameRu,
    description_ru: null, description_en: null, base_price: 30000,
    image_url: null, available: true, archived: false, sort_order: 0,
    created_at: null, updated_at: null, size_options: [], modifiers: [],
    availability: 'available',
  };
}
const item1 = makeItem(10, 1, 'Лате');
const item2 = makeItem(11, 2, 'Сэндвич');
const item3 = makeItem(12, 3, 'Кружка');

function renderPage() {
  return render(
    <MemoryRouter>
      <MenuPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('MenuPage', () => {
  it('renders categories in sort_order (10 < 20 < 30)', async () => {
    (menuApi.listCategories as Mock).mockResolvedValue([cat3, cat1, cat2]);
    (menuApi.listMenuItems as Mock).mockResolvedValue([item1, item2, item3]);

    renderPage();

    await waitFor(() => {
      const headings = screen.getAllByRole('heading', { level: 2 });
      expect(headings[0].textContent).toContain('Напитки');
      expect(headings[1].textContent).toContain('Еда');
      expect(headings[2].textContent).toContain('Товары');
    });
  });

  it('renders empty-state when zero categories', async () => {
    (menuApi.listCategories as Mock).mockResolvedValue([]);
    (menuApi.listMenuItems as Mock).mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('menu.empty')).toBeDefined();
    });
  });

  it('renders retry button on fetch failure', async () => {
    (menuApi.listCategories as Mock).mockRejectedValue(new Error('network'));
    (menuApi.listMenuItems as Mock).mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'menu.retry' })).toBeDefined();
    });
  });

  it('retry button re-invokes listCategories', async () => {
    (menuApi.listCategories as Mock)
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue([]);
    (menuApi.listMenuItems as Mock).mockResolvedValue([]);

    renderPage();

    const retryBtn = await screen.findByRole('button', { name: 'menu.retry' });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(menuApi.listCategories).toHaveBeenCalledTimes(2);
    });
  });
});
