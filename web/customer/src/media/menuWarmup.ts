import { fetchPublicMenu } from '@/api/menu';
import type { PublicMenuItem, PublicMenuResponse } from '@/api/menuTypes';
import {
  hasVideoPlaybackSlot,
  requestVideoPlaybackSlot,
  subscribeVideoPlaybackBudget,
} from './videoPlaybackBudget';

// START_MODULE_CONTRACT
//   PURPOSE: Opportunistically warm customer menu media during login/OTP idle
//            time without competing with visible menu playback.
//   SCOPE:   Browser-only best-effort warmup: menu JSON, first posters, and at
//            most one low-priority video metadata request. No persistence.
//   DEPENDS: @/api/menu, ./videoPlaybackBudget, browser Image/video APIs.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5.2 menu media.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   warmCustomerMenuMedia          - begin bounded login/OTP menu media warmup
//   resetMenuMediaWarmupForTests   - test-only singleton reset
// END_MODULE_MAP

interface ConnectionLike {
  saveData?: boolean;
  effectiveType?: string;
}

interface WarmupOptions {
  posterLimit?: number;
  includeVideo?: boolean;
  videoWarmMs?: number;
}

interface ActiveWarmVideo {
  video: HTMLVideoElement;
  release: () => void;
  unsubscribe: () => void;
  timeoutId: number;
}

const DEFAULT_POSTER_LIMIT = 12;
const DEFAULT_VIDEO_WARM_MS = 8_000;
const menuRequests = new Map<'ru' | 'en', Promise<PublicMenuResponse | null>>();
const warmedPosters = new Set<string>();
const warmedVideos = new Set<string>();
let activeWarmVideo: ActiveWarmVideo | null = null;

function connectionAllowsVideoWarmup(): boolean {
  if (typeof navigator === 'undefined') return false;
  const connection = (navigator as Navigator & { connection?: ConnectionLike })
    .connection;
  if (!connection) return true;
  if (connection.saveData) return false;
  return !/^(slow-)?2g$/i.test(connection.effectiveType ?? '');
}

function loadMenu(language: 'ru' | 'en'): Promise<PublicMenuResponse | null> {
  const existing = menuRequests.get(language);
  if (existing) return existing;

  const request = fetchPublicMenu(language).catch(() => null);
  menuRequests.set(language, request);
  return request;
}

function videoItems(menu: PublicMenuResponse): PublicMenuItem[] {
  return menu.categories.flatMap((category) =>
    category.items.filter(
      (item) =>
        item.media_type === 'video' &&
        item.media_url != null &&
        item.media_poster_url != null,
    ),
  );
}

function warmPoster(url: string): void {
  if (warmedPosters.has(url) || typeof Image === 'undefined') return;
  warmedPosters.add(url);
  const image = new Image();
  image.decoding = 'async';
  image.src = url;
}

function stopWarmVideo(markWarmed: boolean, url: string): void {
  if (!activeWarmVideo) return;
  window.clearTimeout(activeWarmVideo.timeoutId);
  activeWarmVideo.unsubscribe();
  activeWarmVideo.release();
  try {
    activeWarmVideo.video.pause();
  } catch {
    // Best-effort warmup; no user-visible media state depends on this.
  }
  activeWarmVideo.video.removeAttribute('src');
  activeWarmVideo.video.load();
  activeWarmVideo = null;
  if (markWarmed) warmedVideos.add(url);
}

function warmOneVideo(url: string, warmMs: number): void {
  if (
    activeWarmVideo ||
    warmedVideos.has(url) ||
    !connectionAllowsVideoWarmup() ||
    typeof document === 'undefined'
  ) {
    return;
  }

  const slotId = `menu-warmup:${url}`;
  const release = requestVideoPlaybackSlot(slotId, 'warmup');
  const unsubscribe = subscribeVideoPlaybackBudget(() => {
    if (!hasVideoPlaybackSlot(slotId)) {
      stopWarmVideo(false, url);
    }
  });

  if (!hasVideoPlaybackSlot(slotId)) {
    unsubscribe();
    release();
    return;
  }

  const video = document.createElement('video');
  video.muted = true;
  video.playsInline = true;
  video.preload = 'metadata';
  video.src = url;
  video.load();

  const timeoutId = window.setTimeout(() => {
    stopWarmVideo(true, url);
  }, warmMs);
  activeWarmVideo = { video, release, unsubscribe, timeoutId };
}

// START_CONTRACT: warmCustomerMenuMedia
//   PURPOSE: Use login/OTP idle time to warm the menu response, first-screen
//            posters, and optionally one low-priority video metadata request.
//   INPUTS:  language: 'ru' | 'en' — menu locale
//            options?: WarmupOptions — poster/video limits for callers/tests
//   OUTPUTS: void.
//   SIDE_EFFECTS: GET /api/v1/menu via fetchPublicMenu; starts browser image
//                 preloads and at most one budgeted hidden video metadata load.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: warmCustomerMenuMedia
export function warmCustomerMenuMedia(
  language: 'ru' | 'en',
  options: WarmupOptions = {},
): void {
  if (typeof window === 'undefined') return;

  const posterLimit = options.posterLimit ?? DEFAULT_POSTER_LIMIT;
  const includeVideo = options.includeVideo ?? true;
  const videoWarmMs = options.videoWarmMs ?? DEFAULT_VIDEO_WARM_MS;

  void loadMenu(language).then((menu) => {
    if (!menu) return;

    const items = videoItems(menu);
    for (const item of items.slice(0, posterLimit)) {
      if (item.media_poster_url) warmPoster(item.media_poster_url);
    }

    const firstVideoUrl = items[0]?.media_url;
    if (includeVideo && firstVideoUrl) {
      warmOneVideo(firstVideoUrl, videoWarmMs);
    }
  });
}

// START_CONTRACT: resetMenuMediaWarmupForTests
//   PURPOSE: Reset module singleton state between Vitest cases.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: Stops active hidden warmup video and clears warmup caches.
//   LINKS:   web/customer Vitest media tests.
// END_CONTRACT: resetMenuMediaWarmupForTests
export function resetMenuMediaWarmupForTests(): void {
  if (activeWarmVideo) {
    stopWarmVideo(false, '');
  }
  menuRequests.clear();
  warmedPosters.clear();
  warmedVideos.clear();
}
