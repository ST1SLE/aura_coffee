// START_MODULE_CONTRACT
//   PURPOSE: Render static Aura Coffee brand marks from public assets.
//   SCOPE:   BrandMark component for customer app chrome, auth panels, and
//            branded empty media states, plus BrandWordmark for app headers.
//   DEPENDS: web/customer/public/brand/aura-heart-{olive,white}.png,
//            web/customer/public/brand/aura-wordmark-{olive,white}.png.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER; PDD 4.4.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   BrandMark     - presentational Aura Coffee heart logo image
//   BrandWordmark - presentational Aura Coffee wordmark image
// END_MODULE_MAP

type BrandTone = 'olive' | 'white';

interface BrandMarkProps {
  className?: string;
  alt?: string;
  decorative?: boolean;
  tone?: BrandTone;
}

type BrandWordmarkProps = BrandMarkProps;

const BRAND_MARK_SRC: Record<BrandTone, string> = {
  olive: '/brand/aura-heart-olive.png',
  white: '/brand/aura-heart-white.png',
};

const BRAND_WORDMARK_SRC: Record<BrandTone, string> = {
  olive: '/brand/aura-wordmark-olive.png',
  white: '/brand/aura-wordmark-white.png',
};

// START_CONTRACT: BrandMark
//   PURPOSE: Render the Aura Coffee heart logo with optional tone and
//            decorative mode.
//   INPUTS:  className?: string - caller-owned sizing/styling classes;
//            alt?: string - accessible label when not decorative;
//            decorative?: boolean - hide the image from assistive tech;
//            tone?: "olive" | "white" - source variant for light/dark surfaces.
//   OUTPUTS: JSX.Element
//   SIDE_EFFECTS: Browser fetches a /brand/*.png asset; no application state.
//   LINKS:   Layout.tsx, LoginPage.tsx, MenuMedia.tsx.
// END_CONTRACT: BrandMark
export function BrandMark({
  className = '',
  alt = 'Aura Coffee',
  decorative = false,
  tone = 'olive',
}: BrandMarkProps) {
  return (
    <img
      src={BRAND_MARK_SRC[tone]}
      alt={decorative ? '' : alt}
      aria-hidden={decorative ? 'true' : undefined}
      className={['block', className].filter(Boolean).join(' ')}
      draggable={false}
    />
  );
}

// START_CONTRACT: BrandWordmark
//   PURPOSE: Render the Aura Coffee wordmark with optional tone and decorative
//            mode for app chrome and auth panels.
//   INPUTS:  className?: string - caller-owned sizing/styling classes;
//            alt?: string - accessible label when not decorative;
//            decorative?: boolean - hide the image from assistive tech;
//            tone?: "olive" | "white" - source variant for light/dark surfaces.
//   OUTPUTS: JSX.Element
//   SIDE_EFFECTS: Browser fetches a /brand/*.png asset; no application state.
//   LINKS:   Layout.tsx, LoginPage.tsx.
// END_CONTRACT: BrandWordmark
export function BrandWordmark({
  className = '',
  alt = 'Aura Coffee',
  decorative = false,
  tone = 'olive',
}: BrandWordmarkProps) {
  return (
    <img
      src={BRAND_WORDMARK_SRC[tone]}
      alt={decorative ? '' : alt}
      aria-hidden={decorative ? 'true' : undefined}
      className={['block', className].filter(Boolean).join(' ')}
      draggable={false}
    />
  );
}
