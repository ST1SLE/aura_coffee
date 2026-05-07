import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

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

type MockIntersectionObserverEntry = {
  target: Element;
  isIntersecting: boolean;
  intersectionRatio: number;
  boundingClientRect: Pick<DOMRectReadOnly, 'top'>;
};

class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = [];

  readonly observed = new Set<Element>();

  constructor(private readonly callback: IntersectionObserverCallback) {
    MockIntersectionObserver.instances.push(this);
  }

  observe = vi.fn((target: Element) => {
    this.observed.add(target);
  });

  unobserve = vi.fn((target: Element) => {
    this.observed.delete(target);
  });

  disconnect = vi.fn(() => {
    this.observed.clear();
  });

  takeRecords = vi.fn(() => []);

  emit(entries: MockIntersectionObserverEntry[]) {
    this.callback(
      entries as unknown as IntersectionObserverEntry[],
      this as never,
    );
  }
}

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

function renderPageAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/menu/:categoryId" element={<MenuPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockSectionRect(
  id: string,
  rect: Pick<DOMRect, 'top' | 'bottom'>,
) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing section ${id}`);
  Object.defineProperty(node, 'getBoundingClientRect', {
    configurable: true,
    value: () => rect,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockI18n.language = 'ru';
  languageChangedHandlers.length = 0;
  MockIntersectionObserver.instances.length = 0;
  Object.defineProperty(globalThis, 'IntersectionObserver', {
    writable: true,
    value: MockIntersectionObserver,
  });
  Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  });
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

  it('moves focus into item detail and restores it to the opening card', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1],
    });

    renderPage();

    const card = await screen.findByRole('button', { name: /Лате/ });
    fireEvent.click(card);

    const closeButton = await screen.findByRole('button', {
      name: 'menu.close',
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(closeButton);
    });

    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(card);
    });
  });

  it('renders only the sticky category rail, without the duplicate hero copy', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    const cat2 = makeCategory(2, 'Еда', 20, [makeItem(12, 'Сэндвич')]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2],
    });

    renderPage();

    await screen.findByRole('heading', { name: 'menu.title' });

    expect(screen.queryByText('menu.categories')).toBeNull();
    expect(screen.getAllByRole('button', { name: 'Напитки' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Еда' })).toHaveLength(1);
  });

  it('syncs the active category with the section visible in scroll', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    const cat2 = makeCategory(2, 'Еда', 20, [makeItem(12, 'Сэндвич')]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2],
    });

    renderPage();

    const drinksButton = await screen.findByRole('button', { name: 'Напитки' });
    const foodButton = screen.getByRole('button', { name: 'Еда' });
    expect(drinksButton.className).toContain('bg-primary');

    mockSectionRect('menu-category-1', { top: -520, bottom: 40 });
    mockSectionRect('menu-category-2', { top: 120, bottom: 760 });

    await act(async () => {
      window.dispatchEvent(new Event('scroll'));
    });

    await waitFor(() => {
      expect(foodButton.className).toContain('bg-primary');
      expect(drinksButton.className).not.toContain('bg-primary');
    });
  });

  it('activates the final category when the viewport reaches page bottom', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    const cat2 = makeCategory(2, 'Фреш', 20, [makeItem(12, 'Апельсин')]);
    const cat3 = makeCategory(3, 'Молочные коктейли', 30, [
      makeItem(13, 'Ванильный'),
    ]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2, cat3],
    });

    renderPage();

    const drinksButton = await screen.findByRole('button', { name: 'Напитки' });
    const freshButton = screen.getByRole('button', { name: 'Фреш' });
    const milkshakesButton = screen.getByRole('button', {
      name: 'Молочные коктейли',
    });

    mockSectionRect('menu-category-1', { top: -900, bottom: -520 });
    mockSectionRect('menu-category-2', { top: -160, bottom: 172 });
    mockSectionRect('menu-category-3', { top: 204, bottom: 840 });
    Object.defineProperty(window, 'scrollY', {
      configurable: true,
      value: 7137,
    });
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      value: 900,
    });
    Object.defineProperty(document.documentElement, 'scrollHeight', {
      configurable: true,
      value: 8037,
    });

    await act(async () => {
      window.dispatchEvent(new Event('scroll'));
    });

    await waitFor(() => {
      expect(milkshakesButton.className).toContain('bg-primary');
      expect(freshButton.className).not.toContain('bg-primary');
      expect(drinksButton.className).not.toContain('bg-primary');
    });
  });

  it('honors /menu/:categoryId by activating and scrolling to that category', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    const cat2 = makeCategory(2, 'Еда', 20, [makeItem(12, 'Сэндвич')]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2],
    });

    renderPageAt('/menu/2');

    const drinksButton = await screen.findByRole('button', { name: 'Напитки' });
    const foodButton = screen.getByRole('button', { name: 'Еда' });

    await waitFor(() => {
      expect(foodButton.className).toContain('bg-primary');
      expect(drinksButton.className).not.toContain('bg-primary');
      expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith({
        block: 'start',
      });
    });
  });

  it('falls back to the first visible category for an invalid route category', async () => {
    const cat1 = makeCategory(1, 'Напитки', 10, [makeItem(10, 'Лате')]);
    const cat2 = makeCategory(2, 'Еда', 20, [makeItem(12, 'Сэндвич')]);
    (menuApi.fetchPublicMenu as Mock).mockResolvedValue({
      categories: [cat1, cat2],
    });

    renderPageAt('/menu/not-a-category');

    const drinksButton = await screen.findByRole('button', { name: 'Напитки' });
    const foodButton = screen.getByRole('button', { name: 'Еда' });

    await waitFor(() => {
      expect(drinksButton.className).toContain('bg-primary');
      expect(foodButton.className).not.toContain('bg-primary');
      const scrollCalls = (window.HTMLElement.prototype.scrollIntoView as Mock)
        .mock.calls;
      expect(
        scrollCalls.some(([options]) => {
          return (
            typeof options === 'object' &&
            options !== null &&
            'block' in options &&
            options.block === 'start'
          );
        }),
      ).toBe(false);
    });
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
