import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MenuMedia } from './MenuMedia';
import type { PublicMenuItem } from '@/api/menuTypes';

type MockIntersectionObserverEntry = {
  target: Element;
  isIntersecting: boolean;
  intersectionRatio?: number;
};

class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = [];

  readonly observed = new Set<Element>();

  constructor(
    private readonly callback: IntersectionObserverCallback,
    readonly options?: IntersectionObserverInit,
  ) {
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
      entries.map((entry) => ({
        ...entry,
        intersectionRatio:
          entry.intersectionRatio ?? (entry.isIntersecting ? 1 : 0),
      })) as unknown as IntersectionObserverEntry[],
      this as never,
    );
  }
}

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

let playSpy: ReturnType<typeof vi.spyOn>;
let pauseSpy: ReturnType<typeof vi.spyOn>;

function mockMediaQueries({
  reducedMotion = false,
  finePointer = false,
  anyFinePointer = finePointer,
}: {
  reducedMotion?: boolean;
  finePointer?: boolean;
  anyFinePointer?: boolean;
}) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('prefers-reduced-motion')
        ? reducedMotion
        : query.includes('any-pointer')
          ? anyFinePointer
          : finePointer,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

function mockReducedMotion(matches: boolean) {
  mockMediaQueries({ reducedMotion: matches });
}

describe('MenuMedia', () => {
  beforeEach(() => {
    MockIntersectionObserver.instances.length = 0;
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: undefined,
    });
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: undefined,
    });
    Object.defineProperty(window, 'requestAnimationFrame', {
      configurable: true,
      writable: true,
      value: (callback: FrameRequestCallback) => {
        return window.setTimeout(() => callback(0), 0);
      },
    });
    Object.defineProperty(window, 'cancelAnimationFrame', {
      configurable: true,
      writable: true,
      value: (frameId: number) => window.clearTimeout(frameId),
    });
    vi.spyOn(window.HTMLMediaElement.prototype, 'load').mockImplementation(
      () => undefined,
    );
    playSpy = vi
      .spyOn(window.HTMLMediaElement.prototype, 'play')
      .mockResolvedValue(undefined);
    pauseSpy = vi
      .spyOn(window.HTMLVideoElement.prototype, 'pause')
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

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
    expect(video.autoplay).toBe(false);
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

  it('plays desktop video only while the pointer is near the product', async () => {
    mockMediaQueries({ finePointer: true });
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });

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

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    const wrapper = video.parentElement?.parentElement as HTMLElement;
    Object.defineProperty(wrapper, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({
        top: 100,
        right: 200,
        bottom: 200,
        left: 100,
        width: 100,
        height: 100,
        x: 100,
        y: 100,
        toJSON: () => undefined,
      }),
    });

    expect(video.getAttribute('src')).toBeNull();
    expect(MockIntersectionObserver.instances).toHaveLength(1);

    act(() => {
      MockIntersectionObserver.instances[0].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0 },
      ]);
    });

    await waitFor(() => {
      expect(video.getAttribute('src')).toContain('/media/menu/latte/hero.mp4');
    });
    expect(playSpy).not.toHaveBeenCalled();

    act(() => {
      window.dispatchEvent(
        new MouseEvent('pointermove', { clientX: 80, clientY: 150 }),
      );
    });

    await waitFor(() => {
      expect(playSpy).toHaveBeenCalled();
    });

    act(() => {
      window.dispatchEvent(
        new MouseEvent('pointermove', { clientX: 20, clientY: 20 }),
      );
    });

    await waitFor(() => {
      expect(pauseSpy).toHaveBeenCalled();
    });
  });

  it('uses pointer proximity when a fine cursor is available on hybrid desktop devices', async () => {
    mockMediaQueries({ finePointer: false, anyFinePointer: true });
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });

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

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    const wrapper = video.parentElement?.parentElement as HTMLElement;
    Object.defineProperty(wrapper, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({
        top: 100,
        right: 200,
        bottom: 200,
        left: 100,
        width: 100,
        height: 100,
        x: 100,
        y: 100,
        toJSON: () => undefined,
      }),
    });

    expect(MockIntersectionObserver.instances).toHaveLength(1);
    expect(video.getAttribute('src')).toBeNull();

    act(() => {
      MockIntersectionObserver.instances[0].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0 },
      ]);
    });

    await waitFor(() => {
      expect(video.getAttribute('src')).toContain('/media/menu/latte/hero.mp4');
    });
    expect(playSpy).not.toHaveBeenCalled();

    act(() => {
      window.dispatchEvent(
        new MouseEvent('pointermove', { clientX: 150, clientY: 150 }),
      );
    });

    await waitFor(() => {
      expect(playSpy).toHaveBeenCalled();
    });
  });

  it('loads mobile video near the viewport and plays only while visible', async () => {
    mockMediaQueries({ finePointer: false });
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });

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

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    const wrapper = video.parentElement as HTMLElement;
    expect(video.getAttribute('src')).toBeNull();
    expect(MockIntersectionObserver.instances).toHaveLength(2);

    act(() => {
      MockIntersectionObserver.instances[0].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0 },
      ]);
    });

    await waitFor(() => {
      expect(video.getAttribute('src')).toContain('/media/menu/latte/hero.mp4');
    });
    expect(playSpy).not.toHaveBeenCalled();

    act(() => {
      MockIntersectionObserver.instances[1].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0.4 },
      ]);
    });

    await waitFor(() => {
      expect(playSpy).toHaveBeenCalled();
    });

    const pauseCount = pauseSpy.mock.calls.length;
    act(() => {
      MockIntersectionObserver.instances[1].emit([
        { target: wrapper, isIntersecting: false, intersectionRatio: 0 },
      ]);
    });

    await waitFor(() => {
      expect(pauseSpy.mock.calls.length).toBeGreaterThan(pauseCount);
    });
  });

  it('keeps the poster visible while requested playback is buffering', async () => {
    mockMediaQueries({ finePointer: false });
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });

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

    const video = screen.getByLabelText('Latte') as HTMLVideoElement;
    const wrapper = video.parentElement?.parentElement as HTMLElement;
    const posterOverlay = screen.getByTestId('menu-media-poster-overlay');

    act(() => {
      MockIntersectionObserver.instances[0].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0 },
      ]);
      MockIntersectionObserver.instances[1].emit([
        { target: wrapper, isIntersecting: true, intersectionRatio: 0.4 },
      ]);
    });

    await waitFor(() => {
      expect(playSpy).toHaveBeenCalled();
    });
    expect(posterOverlay.className).toContain('opacity-100');

    fireEvent.canPlay(video);
    const playCountAfterCanPlay = playSpy.mock.calls.length;
    expect(playCountAfterCanPlay).toBeGreaterThan(1);

    fireEvent.playing(video);
    await waitFor(() => {
      expect(posterOverlay.className).toContain('opacity-0');
    });

    fireEvent.waiting(video);
    await waitFor(() => {
      expect(posterOverlay.className).toContain('opacity-100');
    });
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

  it('renders branded fallback art when no media source exists', () => {
    const { container } = render(<MenuMedia item={makeItem()} alt="Latte" />);

    expect(screen.queryByAltText('Latte')).toBeNull();
    expect(container.querySelector('video')).toBeNull();
    expect(screen.getByTestId('menu-media-fallback')).toBeDefined();
    expect(
      container.querySelector('img[src="/brand/aura-heart-olive.png"]'),
    ).toBeDefined();
  });
});
