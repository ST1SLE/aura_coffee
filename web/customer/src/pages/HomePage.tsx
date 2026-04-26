import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Landing page for authenticated customers — title, tagline, CTA
//            link to the menu. Pure presentation.
//   SCOPE:   HomePage component.
//   DEPENDS: react-router-dom, react-i18next, @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   HomePage  - / route landing page (pure presentation)
// END_MODULE_MAP

export function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="p-4 flex flex-col items-center gap-6 pt-16">
      <h1 className="text-2xl font-bold">{t('pages.home.title')}</h1>
      <p className="text-muted-foreground text-center">{t('pages.home.description')}</p>
      <Button asChild>
        <Link to="/menu">{t('nav.menu')}</Link>
      </Button>
    </div>
  );
}
