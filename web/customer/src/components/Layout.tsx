import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useAuth } from '@/auth/useAuth';

// START_MODULE_CONTRACT
//   PURPOSE: App shell — sticky header with logo + nav links + logout +
//            LanguageSwitcher, the <main> outlet, and a mobile bottom nav.
//            Wraps all authenticated routes (see App.tsx).
//   SCOPE:   Layout component.
//   DEPENDS: react-router-dom (Outlet/Link/useNavigate), react-i18next,
//            @/components/LanguageSwitcher, @/auth/useAuth.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Layout  - app shell (header + Outlet + bottom nav)
// END_MODULE_MAP

// START_CONTRACT: Layout
//   PURPOSE: Render the app shell and provide the <Outlet/> for nested routes.
//   INPUTS:  none.
//   OUTPUTS: JSX — header + main + mobile bottom nav, with Outlet inside main.
//   SIDE_EFFECTS: handleLogout calls useAuth().logout (which clears tokens +
//                 calls /auth/logout) then navigates to /login.
//                 INV-002 — server enforces auth; this nav is UX only.
//   LINKS:   App.tsx wraps protected routes with this layout.
// END_CONTRACT: Layout
export function Layout() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <Link to="/" className="text-lg font-bold text-brand-700">
          {t('appTitle')}
        </Link>

        <div className="hidden md:flex items-center gap-4">
          <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.menu')}
          </Link>
          <Link to="/cart" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.cart')}
          </Link>
          <Link to="/orders" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.orders')}
          </Link>
          <Link to="/profile" className="text-sm text-muted-foreground hover:text-foreground">
            {t('nav.profile')}
          </Link>
          <button
            onClick={handleLogout}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {t('nav.logout')}
          </button>
          <LanguageSwitcher />
        </div>

        <div className="md:hidden">
          <LanguageSwitcher />
        </div>
      </header>

      <main className="flex-1 p-4">
        <Outlet />
      </main>

      <nav
        className="border-t px-4 py-2 flex justify-around md:hidden"
        style={{ paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))' }}
      >
        <Link to="/" className="flex flex-col items-center py-2 px-3 text-sm text-muted-foreground hover:text-foreground">
          {t('nav.menu')}
        </Link>
        <Link to="/cart" className="flex flex-col items-center py-2 px-3 text-sm text-muted-foreground hover:text-foreground">
          {t('nav.cart')}
        </Link>
        <Link to="/orders" className="flex flex-col items-center py-2 px-3 text-sm text-muted-foreground hover:text-foreground">
          {t('nav.orders')}
        </Link>
        <Link to="/profile" className="flex flex-col items-center py-2 px-3 text-sm text-muted-foreground hover:text-foreground">
          {t('nav.profile')}
        </Link>
      </nav>
    </div>
  );
}
