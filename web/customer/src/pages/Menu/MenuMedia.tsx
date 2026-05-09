import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { BrandMark } from '@/components/BrandMark';
import type { MenuMediaType } from '@/api/menuTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Presentational menu media renderer for public menu items, including
//            video media with poster/legacy-image and branded empty fallbacks.
//   SCOPE:   Used by customer menu cards and item detail. Does not affect cart,
//            pricing, availability, or checkout payloads.
//   DEPENDS: react, @/components/BrandMark,
//            @/api/menuTypes (MenuMediaType).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5.2 menu media,
//            INV-004 (media is outside financial flows), INV-015.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   MenuMedia - video/image renderer with viewport/pointer-gated playback
// END_MODULE_MAP

const DESKTOP_POINTER_PROXIMITY_PX = 64;
const MOBILE_PRELOAD_ROOT_MARGIN = '240px 0px';

interface MenuMediaSource {
  media_type: MenuMediaType | null;
  media_url: string | null;
  media_poster_url: string | null;
  image_url: string | null;
}

interface Props {
  item: MenuMediaSource;
  alt: string;
  className?: string;
  controls?: boolean;
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return false;
    }
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return;
    }

    const mediaQuery = window.matchMedia(query);
    if (!mediaQuery) return;

    setMatches(mediaQuery.matches);

    function handleChange(event: MediaQueryListEvent) {
      setMatches(event.matches);
    }

    mediaQuery.addEventListener?.('change', handleChange);
    return () => {
      mediaQuery.removeEventListener?.('change', handleChange);
    };
  }, [query]);

  return matches;
}

function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

function isPointNearElement(
  node: HTMLElement,
  clientX: number,
  clientY: number,
): boolean {
  const rect = node.getBoundingClientRect();
  return (
    clientX >= rect.left - DESKTOP_POINTER_PROXIMITY_PX &&
    clientX <= rect.right + DESKTOP_POINTER_PROXIMITY_PX &&
    clientY >= rect.top - DESKTOP_POINTER_PROXIMITY_PX &&
    clientY <= rect.bottom + DESKTOP_POINTER_PROXIMITY_PX
  );
}

function usePointerProximityPlayback(
  containerRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
): boolean {
  const [shouldPlay, setShouldPlay] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setShouldPlay(false);
      return;
    }

    let frameId: number | null = null;
    let lastPointer: Pick<PointerEvent, 'clientX' | 'clientY'> | null = null;

    function updateFromPointer() {
      frameId = null;
      const node = containerRef.current;
      const next =
        node != null &&
        lastPointer != null &&
        isPointNearElement(node, lastPointer.clientX, lastPointer.clientY);
      setShouldPlay((current) => (current === next ? current : next));
    }

    function scheduleUpdate(event: PointerEvent) {
      lastPointer = event;
      if (frameId != null) return;
      frameId = window.requestAnimationFrame(updateFromPointer);
    }

    function handleViewportChange() {
      if (lastPointer == null || frameId != null) return;
      frameId = window.requestAnimationFrame(updateFromPointer);
    }

    function pausePlayback() {
      lastPointer = null;
      setShouldPlay(false);
    }

    window.addEventListener('pointermove', scheduleUpdate, { passive: true });
    window.addEventListener('scroll', handleViewportChange, { passive: true });
    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('blur', pausePlayback);

    return () => {
      if (frameId != null) window.cancelAnimationFrame(frameId);
      window.removeEventListener('pointermove', scheduleUpdate);
      window.removeEventListener('scroll', handleViewportChange);
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('blur', pausePlayback);
    };
  }, [containerRef, enabled]);

  return shouldPlay;
}

function useViewportPlayback(
  containerRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
): [boolean, boolean] {
  const [shouldLoad, setShouldLoad] = useState(false);
  const [shouldPlay, setShouldPlay] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setShouldLoad(false);
      setShouldPlay(false);
      return;
    }

    if (typeof IntersectionObserver === 'undefined') {
      setShouldLoad(true);
      setShouldPlay(true);
      return;
    }

    const node = containerRef.current;
    if (!node) return;

    const preloadObserver = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldLoad(true);
          preloadObserver.disconnect();
        }
      },
      { rootMargin: MOBILE_PRELOAD_ROOT_MARGIN },
    );

    const playbackObserver = new IntersectionObserver(
      ([entry]) => {
        const visible =
          entry.isIntersecting && (entry.intersectionRatio ?? 0) > 0;
        setShouldPlay(visible);
      },
      { threshold: [0, 0.01] },
    );

    preloadObserver.observe(node);
    playbackObserver.observe(node);
    return () => {
      preloadObserver.disconnect();
      playbackObserver.disconnect();
    };
  }, [containerRef, enabled]);

  return [shouldLoad, shouldPlay];
}

function useVideoPlaybackIntent(
  controls: boolean,
): [RefObject<HTMLDivElement | null>, boolean, boolean] {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const finePointer = useMediaQuery('(hover: hover) and (pointer: fine)');
  const pointerShouldPlay = usePointerProximityPlayback(
    containerRef,
    !controls && finePointer,
  );
  const [viewportShouldLoad, viewportShouldPlay] = useViewportPlayback(
    containerRef,
    !controls && !finePointer,
  );
  const [hasLoaded, setHasLoaded] = useState(false);

  const requestedLoad =
    controls || (finePointer ? pointerShouldPlay : viewportShouldLoad);
  const requestedPlay =
    !controls && (finePointer ? pointerShouldPlay : viewportShouldPlay);

  useEffect(() => {
    if (requestedLoad) setHasLoaded(true);
  }, [requestedLoad]);

  return [containerRef, hasLoaded, hasLoaded && requestedPlay];
}

function fallbackImage(item: MenuMediaSource): string | null {
  if (item.media_type === 'video') {
    return item.media_poster_url ?? item.image_url;
  }
  if (item.media_type === 'image') {
    return item.media_url ?? item.image_url;
  }
  return item.image_url;
}

function requestVideoPlayback(video: HTMLVideoElement | null) {
  if (!video) return;
  try {
    const result = video.play();
    if (result && typeof result.catch === 'function') {
      result.catch(() => undefined);
    }
  } catch {
    // Browsers may still reject autoplay; the poster remains the fallback.
  }
}

// START_CONTRACT: MenuMedia
//   PURPOSE: Render menu video media when available and safe; otherwise render
//            poster, media image, legacy image_url, or branded fallback.
//   INPUTS:  Props { item media fields, alt, className? }.
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: Subscribes to media queries, IntersectionObserver, and
//                 pointer proximity events for video playback only; no network
//                 mutation or cart/order state changes.
//   LINKS:   PDD §5.2 menu media; INV-004; INV-015.
// END_CONTRACT: MenuMedia
export function MenuMedia({
  item,
  alt,
  className = '',
  controls = false,
}: Props) {
  const reducedMotion = usePrefersReducedMotion();
  const [containerRef, shouldLoadVideo, shouldPlayVideo] =
    useVideoPlaybackIntent(controls);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoFailed, setVideoFailed] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);

  const canRenderVideo =
    item.media_type === 'video' &&
    item.media_url != null &&
    item.media_poster_url != null &&
    !reducedMotion &&
    !videoFailed;

  const imageSrc = fallbackImage(item);
  const videoClassName = [
    'h-full w-full object-cover',
    controls ? '' : 'pointer-events-none',
  ]
    .filter(Boolean)
    .join(' ');

  useEffect(() => {
    if (!canRenderVideo || !shouldLoadVideo) return;
    const video = videoRef.current;
    if (!video) return;
    video.load();
  }, [canRenderVideo, item.media_url, shouldLoadVideo]);

  useEffect(() => {
    if (!canRenderVideo || controls || !shouldLoadVideo) return;
    const video = videoRef.current;
    if (!video) return;

    if (shouldPlayVideo) {
      requestVideoPlayback(video);
    } else {
      video.pause();
    }
  }, [canRenderVideo, controls, shouldLoadVideo, shouldPlayVideo]);

  if (!canRenderVideo && (!imageSrc || imageFailed)) {
    return (
      <div
        ref={containerRef}
        aria-hidden="true"
        className={['overflow-hidden bg-secondary', className].join(' ')}
        data-testid="menu-media-fallback"
      >
        <div className="flex h-full w-full items-center justify-center bg-[radial-gradient(circle_at_45%_34%,hsl(var(--card)/0.86),hsl(var(--secondary))_52%,hsl(var(--primary)/0.35)_100%)]">
          <BrandMark
            decorative
            className="h-20 w-20 object-contain drop-shadow-[0_18px_30px_rgba(30,24,19,0.22)]"
          />
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={['overflow-hidden', className].join(' ')}
    >
      {canRenderVideo ? (
        <video
          ref={videoRef}
          aria-label={alt}
          className={videoClassName}
          src={shouldLoadVideo ? (item.media_url ?? undefined) : undefined}
          poster={item.media_poster_url ?? undefined}
          muted
          loop
          playsInline
          controls={controls}
          controlsList="nodownload noplaybackrate noremoteplayback"
          disablePictureInPicture
          preload={shouldLoadVideo ? 'auto' : 'metadata'}
          onClick={controls ? (event) => event.stopPropagation() : undefined}
          onContextMenu={(event) => event.preventDefault()}
          onCanPlay={() => {
            if (!controls && shouldPlayVideo) {
              requestVideoPlayback(videoRef.current);
            }
          }}
          onLoadedData={() => {
            if (!controls && shouldPlayVideo) {
              requestVideoPlayback(videoRef.current);
            }
          }}
          onError={() => setVideoFailed(true)}
        />
      ) : (
        <img
          src={imageSrc ?? undefined}
          alt={alt}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setImageFailed(true)}
        />
      )}
    </div>
  );
}
