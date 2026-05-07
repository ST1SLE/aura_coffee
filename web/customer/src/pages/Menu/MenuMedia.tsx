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
//   MenuMedia - video/image renderer with reduced-motion and error fallbacks
// END_MODULE_MAP

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

function usePrefersReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!mediaQuery) return;

    setReducedMotion(mediaQuery.matches);

    function handleChange(event: MediaQueryListEvent) {
      setReducedMotion(event.matches);
    }

    mediaQuery.addEventListener?.('change', handleChange);
    return () => {
      mediaQuery.removeEventListener?.('change', handleChange);
    };
  }, []);

  return reducedMotion;
}

function useLazyVideo(): [RefObject<HTMLDivElement | null>, boolean] {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    if (shouldLoad) return;
    if (typeof IntersectionObserver === 'undefined') {
      setShouldLoad(true);
      return;
    }

    const node = containerRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [shouldLoad]);

  return [containerRef, shouldLoad];
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
//   SIDE_EFFECTS: Subscribes to prefers-reduced-motion and IntersectionObserver;
//                 no network mutation or cart/order state changes.
//   LINKS:   PDD §5.2 menu media; INV-004; INV-015.
// END_CONTRACT: MenuMedia
export function MenuMedia({
  item,
  alt,
  className = '',
  controls = false,
}: Props) {
  const reducedMotion = usePrefersReducedMotion();
  const [containerRef, shouldLoadVideo] = useLazyVideo();
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
    if (!canRenderVideo || !shouldLoadVideo || controls) return;
    const video = videoRef.current;
    if (!video) return;
    video.load();
    requestVideoPlayback(video);
  }, [canRenderVideo, controls, item.media_url, shouldLoadVideo]);

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
          autoPlay
          controls={controls}
          controlsList="nodownload noplaybackrate noremoteplayback"
          disablePictureInPicture
          preload={shouldLoadVideo ? 'auto' : 'metadata'}
          onClick={controls ? (event) => event.stopPropagation() : undefined}
          onContextMenu={(event) => event.preventDefault()}
          onCanPlay={() => {
            if (!controls) requestVideoPlayback(videoRef.current);
          }}
          onLoadedData={() => {
            if (!controls) requestVideoPlayback(videoRef.current);
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
