// START_MODULE_CONTRACT
//   PURPOSE: Render the static Aura Coffee heart brand mark from public assets.
//   SCOPE:   BrandMark component for customer app chrome, auth panels, and
//            branded empty media states.
//   DEPENDS: web/customer/public/brand/aura-mark.png.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER; PDD 4.4.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   BrandMark - presentational Aura Coffee heart logo image
// END_MODULE_MAP

interface BrandMarkProps {
  className?: string;
  alt?: string;
  decorative?: boolean;
}

const BRAND_MARK_SRC = '/brand/aura-mark.png';

// START_CONTRACT: BrandMark
//   PURPOSE: Render the Aura Coffee heart logo with optional decorative mode.
//   INPUTS:  className?: string - caller-owned sizing/styling classes;
//            alt?: string - accessible label when not decorative;
//            decorative?: boolean - hide the image from assistive tech.
//   OUTPUTS: JSX.Element
//   SIDE_EFFECTS: Browser fetches /brand/aura-mark.png; no application state.
//   LINKS:   Layout.tsx, LoginPage.tsx, MenuMedia.tsx.
// END_CONTRACT: BrandMark
export function BrandMark({
  className = '',
  alt = 'Aura Coffee',
  decorative = false,
}: BrandMarkProps) {
  return (
    <img
      src={BRAND_MARK_SRC}
      alt={decorative ? '' : alt}
      aria-hidden={decorative ? 'true' : undefined}
      className={['block', className].filter(Boolean).join(' ')}
      draggable={false}
    />
  );
}
