import { waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { fetchPublicMenu } from '@/api/menu';
import type { PublicMenuResponse } from '@/api/menuTypes';
import { hasVideoPlaybackSlot, requestVideoPlaybackSlot } from './videoPlaybackBudget';
import {
  resetMenuMediaWarmupForTests,
  warmCustomerMenuMedia,
} from './menuWarmup';
import {
  resetVideoPlaybackBudgetForTests,
  setVideoPlaybackBudgetMaxSlotsForTests,
} from './videoPlaybackBudget';

vi.mock('@/api/menu', () => ({
  fetchPublicMenu: vi.fn(),
}));

const menu: PublicMenuResponse = {
  categories: [
    {
      id: 1,
      type: 'drink',
      name: 'Coffee',
      name_ru: 'Кофе',
      name_en: 'Coffee',
      sort_order: 0,
      items: [
        {
          id: 1,
          category_id: 1,
          name: 'Latte',
          name_ru: 'Латте',
          name_en: 'Latte',
          description: null,
          description_ru: null,
          description_en: null,
          base_price: 25000,
          image_url: null,
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
          available: true,
          sort_order: 0,
          size_options: [],
          modifiers: [],
        },
      ],
    },
  ],
};

describe('menuWarmup', () => {
  beforeEach(() => {
    resetMenuMediaWarmupForTests();
    resetVideoPlaybackBudgetForTests();
    setVideoPlaybackBudgetMaxSlotsForTests(1);
    (fetchPublicMenu as Mock).mockResolvedValue(menu);
    vi.spyOn(window.HTMLMediaElement.prototype, 'load').mockImplementation(
      () => undefined,
    );
    vi.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(
      () => undefined,
    );
  });

  afterEach(() => {
    resetMenuMediaWarmupForTests();
    resetVideoPlaybackBudgetForTests();
    vi.restoreAllMocks();
  });

  it('warms menu posters and one low-priority video', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement');

    warmCustomerMenuMedia('ru', { videoWarmMs: 10_000 });

    await waitFor(() => {
      expect(fetchPublicMenu).toHaveBeenCalledWith('ru');
      expect(createElementSpy).toHaveBeenCalledWith('video');
      expect(hasVideoPlaybackSlot('menu-warmup:/media/menu/latte/hero.mp4')).toBe(
        true,
      );
    });
  });

  it('does not start video warmup when only posters are requested', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement');

    warmCustomerMenuMedia('ru', { includeVideo: false });

    await waitFor(() => {
      expect(fetchPublicMenu).toHaveBeenCalledWith('ru');
    });
    expect(createElementSpy).not.toHaveBeenCalledWith('video');
  });

  it('releases warmup when user playback needs the slot', async () => {
    warmCustomerMenuMedia('ru', { videoWarmMs: 10_000 });

    await waitFor(() => {
      expect(hasVideoPlaybackSlot('menu-warmup:/media/menu/latte/hero.mp4')).toBe(
        true,
      );
    });

    const release = requestVideoPlaybackSlot('visible-card', 'user');

    await waitFor(() => {
      expect(hasVideoPlaybackSlot('menu-warmup:/media/menu/latte/hero.mp4')).toBe(
        false,
      );
      expect(hasVideoPlaybackSlot('visible-card')).toBe(true);
    });

    release();
  });
});
