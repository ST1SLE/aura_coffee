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
    { to: '/menu', label: t('nav.menu'), icon: Coffee },
    { to: '/cart', label: t('nav.cart'), icon: ShoppingBag },
    { to: '/orders', label: t('nav.orders'), icon: ReceiptText },
    { to: '/profile', label: t('nav.profile'), icon: User },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-background/90 px-4 py-3 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3">
          <Link
            to="/menu"
            className="flex min-w-0 items-center gap-3 text-base font-semibold tracking-normal text-foreground"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-[0_10px_24px_rgba(247,193,70,0.22)]">
              <Coffee className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className="block truncate leading-tight">{t('appTitle')}</span>
              <span className="block truncate text-xs font-normal text-muted-foreground">
                {t('pages.home.description')}
              </span>
            </span>
          </Link>

          <div className="hidden items-center gap-2 md:flex">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/menu'}
                className={({ isActive }) =>
                  [
                    'inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground',
                  ].join(' ')
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground"
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

      <main className="mx-auto w-full max-w-6xl flex-1 pb-28 md:pb-10">
        <Outlet />
      </main>

      <nav
        className="fixed bottom-0 left-0 right-0 z-40 w-screen max-w-full overflow-hidden px-3 py-3 md:hidden"
        style={{
          width: '100vw',
          maxWidth: '100vw',
          boxSizing: 'border-box',
          paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))',
        }}
      >
        <div className="relative mx-auto h-14 max-w-sm rounded-full border border-white/10 bg-background/95 shadow-[0_-12px_40px_rgba(0,0,0,0.32)] backdrop-blur-xl">
          {navItems.map(({ to, label, icon: Icon }, index) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/menu'}
              aria-label={label}
              style={{
                left: `${12.5 + index * 25}%`,
                minWidth: 0,
                transform: 'translate(-50%, -50%)',
              }}
              className={({ isActive }) =>
                [
                  'absolute top-1/2 flex h-11 w-11 items-center justify-center rounded-full transition-colors',
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
