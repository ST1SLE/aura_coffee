import { Outlet, Link, NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Coffee, LogOut, ReceiptText, ShoppingBag, User } from 'lucide-react';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useAuth } from '@/auth/useAuth';

// START_MODULE_CONTRACT
//   PURPOSE: Dark mobile-first app shell — sticky header with logo + nav links
//            + logout + LanguageSwitcher, the <main> outlet, and a mobile
//            bottom nav.
//            Wraps all authenticated routes (see App.tsx).
//   SCOPE:   Layout component.
//   DEPENDS: react-router-dom (Outlet/Link/NavLink/useNavigate), react-i18next,
//            lucide-react, @/components/LanguageSwitcher, @/auth/useAuth.
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

  const navItems = [
    { to: '/', label: t('nav.menu'), icon: Coffee },
    { to: '/cart', label: t('nav.cart'), icon: ShoppingBag },
    { to: '/orders', label: t('nav.orders'), icon: ReceiptText },
    { to: '/profile', label: t('nav.profile'), icon: User },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 text-base font-semibold tracking-normal text-foreground"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Coffee className="h-5 w-5" aria-hidden="true" />
            </span>
            {t('appTitle')}
          </Link>

          <div className="hidden md:flex items-center gap-4">
            {navItems.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  [
                    'text-sm transition-colors',
                    isActive
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  ].join(' ')
                }
              >
                {label}
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              {t('nav.logout')}
            </button>
            <LanguageSwitcher />
          </div>

          <div className="md:hidden">
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 pb-24 md:pb-8">
        <Outlet />
      </main>

      <nav
        className="fixed bottom-0 left-0 right-0 z-40 w-screen max-w-full overflow-hidden border-t border-border/80 bg-background/95 px-3 py-2 backdrop-blur md:hidden"
        style={{
          width: '100vw',
          maxWidth: '100vw',
          boxSizing: 'border-box',
          paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))',
        }}
      >
        <div className="relative h-12">
          {navItems.map(({ to, label, icon: Icon }, index) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              aria-label={label}
              style={{
                left: `${12.5 + index * 25}vw`,
                minWidth: 0,
                transform: 'translateX(-50%)',
              }}
              className={({ isActive }) =>
                [
                  'absolute top-0 flex h-12 w-12 items-center justify-center rounded-md transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                ].join(' ')
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
