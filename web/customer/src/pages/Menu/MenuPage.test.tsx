import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// Мутируемый мок i18n для эмуляции смены языка
const languageChangedHandlers: ((lang: string) => void)[] = [];
const mockI18n = {
  language: 'ru' as string,
  on: vi.fn((event: string, handler: (lang: string) => void) => {
    if (event === 'languageChanged') languageChangedHandlers.push(handler);
  }),
  off: vi.fn(),
  changeLanguage: async (lang: string) => {
    mockI18n.language = lang;
    languageChangedHandlers.forEach((h) => h(lang));
  },
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: mockI18n,
  }),
}));
vi.mock('@/api/menu', () => ({
  fetchPublicMenu: vi.fn(),
}));
vi.mock('@/store/cart', () => ({
  useCartStore: vi.fn(() => vi.fn()),
}));

import * as menuApi from '@/api/menu';
import { MenuPage } from './MenuPage';
import type { PublicCategory, PublicMenuItem } from '@/api/menuTypes';

function makeItem(id: number, name: string): PublicMenuItem {
  return {
    id,
    category_id: 1,
    name,
    name_ru: name,
    name_en: name,
    description: null,
    description_ru: null,
    description_en: null,
    base_price: 30000,
    image_url: null,
    media_type: null,
    media_url: null,
    media_poster_url: null,
    available: true,
    sort_order: 0,
    size_options: [],
    modifiers: [],
  };
}

function makeCategory(
  id: number,
  name: string,
  sort_order: number,
  items: PublicMenuItem[] = [],
): PublicCategory {
  return {
    id,
    type: 'drink',
    name,
    name_ru: name,
    name_en: name,
    sort_order,
    items,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <MenuPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockI18n.language = 'ru';
  languageChangedHandlers.length = 0;
});

describe('MenuPage', () => {
  // Задача 3.1: категории рендерятся в порядке, возвращённом сервером (без клиентской сортировки)
  it('renders categories in server-returned order', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [
      makeItem(10, 'Лате'),
      makeItem(11, 'Капучино'),
    ]);
    const cat2 = makeCategory(2, 'Еда', 20, [
      makeItem(12, 'Сэндвич'),
      makeItem(13, 'Круассан'),
    ]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2],
    });

    renderPage();

    const headings = await screen.findAllByRole('heading', { level: 2 });
    expect(headings[0].textContent).toContain('Напитки');
    expect(headings[1].textContent).toContain('Еда');
  });

  it('renders empty-state when zero categories', async () => {
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({ categories: [] });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('menu.empty')).toBeDefined();
    });
  });

  it('renders retry button on fetch failure', async () => {
    (menuApi.fetchPublicMenu as Mock).mockRejectedValue(new Error('network'));

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'menu.retry' })).toBeDefined();
    });
  });

  it('retry button re-invokes fetchPublicMenu', async () => {
    (menuApi.fetchPublicMenu as Mock)
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue({ categories: [] });

    renderPage();

    const retryBtn = await screen.findByRole('button', { name: 'menu.retry' });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(menuApi.fetchPublicMenu).toHaveBeenCalledTimes(2);
    });
  });

  // Задача 3.2: перезагрузка при смене языка i18n
  it('MenuPage refetches when i18n language changes', async () => {
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({ categories: [] });

    renderPage();

    await waitFor(() => {
      expect(menuApi.fetchPublicMenu).toHaveBeenCalledWith('ru');
    });

    await act(async () => {
      await mockI18n.changeLanguage('en');
    });

    await waitFor(() => {
      expect(menuApi.fetchPublicMenu).toHaveBeenCalledWith('en');
      expect(menuApi.fetchPublicMenu).toHaveBeenCalledTimes(2);
    });
  });
});
