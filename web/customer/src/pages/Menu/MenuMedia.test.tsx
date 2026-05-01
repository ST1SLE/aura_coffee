import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MenuMedia } from './MenuMedia';
import type { PublicMenuItem } from '@/api/menuTypes';

function makeItem(overrides: Partial<PublicMenuItem> = {}): PublicMenuItem {
  return {
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

function mockReducedMotion(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('MenuMedia', () => {
  it('renders muted inline video for video media', () => {
    render(
      <MenuMedia
        item={makeItem({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        })}
        alt="Latte"
        className="h-24"
      />,
    );

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    expect(video.tagName).toBe('VIDEO');
    expect(video.muted).toBe(true);
    expect(video.loop).toBe(true);
    expect(video.playsInline).toBe(true);
    expect(video.controls).toBe(false);
    expect(video.className).toContain('pointer-events-none');
    expect(video.poster).toContain('/media/menu/latte/poster.webp');
  });

  it('can expose native controls only when explicitly requested', () => {
    render(
      <MenuMedia
        item={makeItem({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        })}
        alt="Latte"
        controls
      />,
    );

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    expect(video.controls).toBe(true);
    expect(video.className).not.toContain('pointer-events-none');
  });

  it('uses poster fallback when reduced-motion is preferred', () => {
    mockReducedMotion(true);

    render(
      <MenuMedia
        item={makeItem({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        })}
        alt="Latte"
      />,
    );

    const image = screen.getByAltText('Latte') as HTMLImageElement;
    expect(image.src).toContain('/media/menu/latte/poster.webp');
  });

  it('falls back to poster when video loading fails', () => {
    render(
      <MenuMedia
        item={makeItem({
          media_type: 'video',
          media_url: '/media/menu/latte/hero.mp4',
          media_poster_url: '/media/menu/latte/poster.webp',
        })}
        alt="Latte"
      />,
    );

    fireEvent.error(screen.getByLabelText('Latte'));

    const image = screen.getByAltText('Latte') as HTMLImageElement;
    expect(image.src).toContain('/media/menu/latte/poster.webp');
  });

  it('prefers image media over legacy image_url', () => {
    render(
      <MenuMedia
        item={makeItem({
          image_url: '/legacy/latte.jpg',
          media_type: 'image',
          media_url: '/media/menu/latte/poster.webp',
        })}
        alt="Latte"
      />,
    );

    const image = screen.getByAltText('Latte') as HTMLImageElement;
    expect(image.src).toContain('/media/menu/latte/poster.webp');
  });

  it('falls back to legacy image_url when media fields are missing', () => {
    render(
      <MenuMedia
        item={makeItem({ image_url: '/legacy/latte.jpg' })}
        alt="Latte"
      />,
    );

    const image = screen.getByAltText('Latte') as HTMLImageElement;
    expect(image.src).toContain('/legacy/latte.jpg');
  });
});
