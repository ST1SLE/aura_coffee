import { describe, it, test, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listCategories,
  createCategory,
  createItem,
  createModifier,
  createSize,
  setItemAvailability,
  deleteCategory,
  ApiError,
} from './menu';
import type {
  CategoryCreate,
  MenuItemCreate,
  ModifierCreate,
  SizeOptionCreate,
} from './menu';

describe('api/menu', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
    // Токен для прохождения authenticatedFetch без авторизации
    localStorage.setItem('accessToken', 'test');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockJson(body: unknown, status = 200) {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  }

  it('listCategories — GET /api/v1/admin/menu/categories', async () => {
    const data = [
      {
        id: 1,
        type: 'drink',
        name_ru: 'Кофе',
        name_en: 'Coffee',
        sort_order: 0,
        is_visible: true,
      },
    ];
    mockJson(data);

    const result = await listCategories();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/api/v1/admin/menu/categories');
    expect(result).toEqual(data);
  });

  it('createItem — POST /api/v1/admin/menu/items', async () => {
    const created = {
      id: 10,
      category_id: 1,
      name_ru: 'Латте',
      name_en: 'Latte',
      base_price: 35000,
      available: true,
      archived: false,
      sort_order: 0,
      size_options: [],
      modifiers: [],
    };
    mockJson(created, 201);

    const result = await createItem({
      category_id: 1,
      name_ru: 'Латте',
      name_en: 'Latte',
      base_price: 35000,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/admin/menu/items');
    expect(init.method).toBe('POST');
    expect(result).toMatchObject({ id: 10, name_ru: 'Латте' });
  });

  it('setItemAvailability — PATCH с телом { available: false }', async () => {
    const updated = { id: 5, availability: 'stop_list' };
    mockJson(updated);

    await setItemAvailability(5, false);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/items/5/availability');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ available: false });
  });

  it('deleteCategory 409 — бросает ApiError(409)', async () => {
    mockJson({ detail: 'referenced' }, 409);

    const err = await deleteCategory(1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
  });

  // ── 1.1 CategoryCreate TS-контракт ──────────────────────────────────────────

  test('CategoryCreate requires name_ru, name_en, type, sort_order, is_visible', () => {
    // @ts-expect-error — монолингвальный литерал не совместим с CategoryCreate
    const _bad: CategoryCreate = { name: 'x' };
    void _bad;

    // Билингвальный литерал совместим
    const _good: CategoryCreate = {
      type: 'drink',
      name_ru: 'Кофе',
      name_en: 'Coffee',
      sort_order: 0,
      is_visible: true,
    };
    expect(_good.type).toBe('drink');
  });

  // ── 1.2 createCategory отправляет билингвальный payload ─────────────────────

  test('createCategory POSTs bilingual payload', async () => {
    const payload = {
      type: 'drink' as const,
      name_ru: 'Кофе',
      name_en: 'Coffee',
      sort_order: 0,
      is_visible: true,
    };
    mockJson({ id: 1, ...payload });

    await createCategory(payload);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });

  // ── 2.1 MenuItemCreate TS-контракт ──────────────────────────────────────────

  test('MenuItemCreate requires name_ru, name_en, base_price', () => {
    // @ts-expect-error — старый монолингвальный литерал не совместим
    const _bad: MenuItemCreate = { name: 'Латте', price_kopecks: 35000 };
    void _bad;

    const _good: MenuItemCreate = {
      category_id: 1,
      name_ru: 'Латте',
      name_en: 'Latte',
      base_price: 35000,
      media_type: 'video',
      media_url: '/media/menu/latte/hero.mp4',
      media_poster_url: '/media/menu/latte/poster.webp',
    };
    expect(_good.base_price).toBe(35000);
    expect(_good.media_type).toBe('video');
  });

  // ── 2.2 createItem отправляет билингвальный payload с base_price ─────────────

  test('createItem POSTs bilingual payload with base_price', async () => {
    const payload: MenuItemCreate = {
      category_id: 1,
      name_ru: 'Латте',
      name_en: 'Latte',
      base_price: 35000,
      media_type: 'video',
      media_url: '/media/menu/latte/hero.mp4',
      media_poster_url: '/media/menu/latte/poster.webp',
    };
    mockJson(
      {
        id: 10,
        ...payload,
        available: true,
        archived: false,
        sort_order: 0,
        size_options: [],
        modifiers: [],
      },
      201,
    );

    await createItem(payload);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const sent = JSON.parse(init.body as string);
    expect(sent).toMatchObject({
      name_ru: 'Латте',
      name_en: 'Latte',
      base_price: 35000,
      media_type: 'video',
      media_url: '/media/menu/latte/hero.mp4',
      media_poster_url: '/media/menu/latte/poster.webp',
    });
    expect(sent).not.toHaveProperty('name');
    expect(sent).not.toHaveProperty('price_kopecks');
  });

  // ── 3.1 ModifierCreate TS-контракт ──────────────────────────────────────────

  test('ModifierCreate requires name_ru, name_en, price', () => {
    // @ts-expect-error — монолингвальный литерал не совместим
    const _bad: ModifierCreate = { name: 'Ваниль', price_kopecks: 5000 };
    void _bad;

    const _good: ModifierCreate = {
      name_ru: 'Ваниль',
      name_en: 'Vanilla',
      price: 5000,
    };
    expect(_good.price).toBe(5000);
  });

  // ── 3.2 createModifier отправляет билингвальный payload ─────────────────────

  test('createModifier POSTs bilingual payload', async () => {
    const payload: ModifierCreate = {
      name_ru: 'Ваниль',
      name_en: 'Vanilla',
      price: 5000,
    };
    mockJson({ id: 3, ...payload, available: true, sort_order: 0 });

    await createModifier(payload);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const sent = JSON.parse(init.body as string);
    expect(sent).toMatchObject({
      name_ru: 'Ваниль',
      name_en: 'Vanilla',
      price: 5000,
    });
    expect(sent).not.toHaveProperty('name');
    expect(sent).not.toHaveProperty('price_kopecks');
  });

  // ── 4.1 SizeOptionCreate TS-контракт ────────────────────────────────────────

  test('SizeOptionCreate requires label: SizeLabel and price', () => {
    const _bad: SizeOptionCreate = {
      // @ts-expect-error — старый label не совместим с SizeLabel
      label: 'Small',
      volume_ml: 200,
      price_kopecks: 15000,
    };
    void _bad;

    const _good: SizeOptionCreate = {
      menu_item_id: 1,
      label: 'S',
      price: 1500,
      available: true,
    };
    expect(_good.label).toBe('S');
  });

  // ── 4.2 createSize отправляет enum label и price ─────────────────────────────

  test('createSize POSTs enum label and price', async () => {
    const payload: SizeOptionCreate = {
      menu_item_id: 1,
      label: 'S',
      price: 1500,
      available: true,
    };
    mockJson({ id: 5, ...payload });

    await createSize(payload);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const sent = JSON.parse(init.body as string);
    expect(sent).toMatchObject({ label: 'S', price: 1500 });
    expect(sent).not.toHaveProperty('price_kopecks');
    expect(sent).not.toHaveProperty('volume_ml');
  });
});
