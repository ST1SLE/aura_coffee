import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { MenuMediaType } from '@/api/menuTypes';

// START_MODULE_CONTRACT
//   PURPOSE: Presentational menu media renderer for public menu items, including
//            video media with poster/legacy-image fallback.
//   SCOPE:   Used by customer menu cards and item detail. Does not affect cart,
//            pricing, availability, or checkout payloads.
//   DEPENDS: react, @/api/menuTypes (MenuMediaType).
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

// START_CONTRACT: MenuMedia
//   PURPOSE: Render menu video media when available and safe; otherwise render
//            poster, media image, legacy image_url, or nothing.
//   INPUTS:  Props { item media fields, alt, className? }.
//   OUTPUTS: JSX.Element | null.
//   SIDE_EFFECTS: Subscribes to prefers-reduced-motion and IntersectionObserver;
//                 no network mutation or cart/order state changes.
//   LINKS:   PDD §5.2 menu media; INV-004; INV-015.
// END_CONTRACT: MenuMedia
export function MenuMedia({
  item,
  alt,
  className = '',
  controls = true,
}: Props) {
  const reducedMotion = usePrefersReducedMotion();
  const [containerRef, shouldLoadVideo] = useLazyVideo();
  const [videoFailed, setVideoFailed] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);

  const canRenderVideo =
    item.media_type === 'video' &&
    item.media_url != null &&
    item.media_poster_url != null &&
    !reducedMotion &&
    !videoFailed;

  const imageSrc = fallbackImage(item);

  if (!canRenderVideo && (!imageSrc || imageFailed)) {
    return (
      <div
        ref={containerRef}
        aria-hidden="true"
        className={['overflow-hidden bg-secondary', className].join(' ')}
      />
    );
  }

  return (
    <div
      ref={containerRef}
      className={['overflow-hidden', className].join(' ')}
    >
      {canRenderVideo ? (
        <video
          aria-label={alt}
          className="h-full w-full object-cover"
          src={shouldLoadVideo ? (item.media_url ?? undefined) : undefined}
          poster={item.media_poster_url ?? undefined}
          muted
          loop
          playsInline
          autoPlay
          controls={controls}
          preload="metadata"
          onClick={(event) => event.stopPropagation()}
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
