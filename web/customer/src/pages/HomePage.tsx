import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Legacy menu CTA page for authenticated customers — title,
//            tagline, CTA link to the real /menu surface. Pure presentation.
//   SCOPE:   HomePage component.
//   DEPENDS: react-router-dom, react-i18next, @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   HomePage  - menu CTA page (pure presentation)
// END_MODULE_MAP

export function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-5 text-center">
      <div className="aura-surface flex w-full max-w-md flex-col items-center gap-4 rounded-lg p-6">
        <h1 className="text-4xl font-semibold tracking-normal">
          {t('pages.home.title')}
        </h1>
        <p className="text-muted-foreground">{t('pages.home.description')}</p>
        <Button asChild>
          <Link to="/menu">{t('nav.menu')}</Link>
        </Button>
      </div>
    </div>
  );
}
