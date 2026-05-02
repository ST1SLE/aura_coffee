import {
  Outlet,
  Link,
  NavLink,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Coffee, LogOut, ReceiptText, ShoppingBag, User } from 'lucide-react';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useAuth } from '@/auth/useAuth';
import { useCartStore } from '@/store/cart';

// START_MODULE_CONTRACT
//   PURPOSE: Dark mobile-first app shell — sticky header with logo + nav links
//            + logout + LanguageSwitcher, the <main> outlet, and a mobile
//            bottom nav, and cart-count affordances when the cart has items.
//            Wraps all authenticated routes (see App.tsx).
//   SCOPE:   Layout component.
//   DEPENDS: react-router-dom (Outlet/Link/NavLink/useLocation/useNavigate),
//            react-i18next, lucide-react, @/components/LanguageSwitcher,
//            @/auth/useAuth, @/store/cart.
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
//            Cart links include count labels/badges when itemCount > 0.
//   SIDE_EFFECTS: handleLogout calls useAuth().logout (which clears tokens +
//                 calls /auth/logout) then navigates to /login.
//                 INV-002 — server enforces auth; this nav is UX only.
//   LINKS:   App.tsx wraps protected routes with this layout.
// END_CONTRACT: Layout
export function Layout() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const itemCount = useCartStore((state) => state.itemCount);
  const cartBadge = itemCount > 99 ? '99+' : String(itemCount);
  const showCartAffordance = itemCount > 0;
  const showFloatingCart =
    showCartAffordance &&
    (location.pathname === '/menu' || location.pathname.startsWith('/menu/'));

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
              <span className="block truncate leading-tight">
                {t('appTitle')}
              </span>
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
                aria-label={
                  to === '/cart' && showCartAffordance
                    ? `${label}: ${itemCount}`
                    : label
                }
                className={({ isActive }) =>
                  [
                    'relative inline-flex h-11 min-w-11 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground',
                  ].join(' ')
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
                {to === '/cart' && showCartAffordance && (
                  <span
                    aria-hidden="true"
                    className="ml-0.5 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[0.68rem] font-semibold leading-5 text-primary-foreground"
                  >
                    {cartBadge}
                  </span>
                )}
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

      {showFloatingCart && (
        <Link
          to="/cart"
          aria-label={`${t('nav.cart')}: ${itemCount}`}
          className="fixed bottom-[calc(5rem+env(safe-area-inset-bottom))] left-1/2 z-50 inline-flex min-h-11 -translate-x-1/2 items-center gap-3 rounded-full border border-white/10 bg-background/95 px-4 py-2 text-sm font-semibold text-foreground shadow-[0_18px_45px_rgba(0,0,0,0.42)] backdrop-blur-xl transition-colors hover:bg-secondary md:hidden"
          data-testid="floating-cart-link"
        >
          <ShoppingBag className="h-4 w-4" aria-hidden="true" />
          <span>{t('nav.cart')}</span>
          <span
            aria-hidden="true"
            className="inline-flex min-w-6 items-center justify-center rounded-full bg-primary px-2 text-xs font-semibold leading-6 text-primary-foreground"
          >
            {cartBadge}
          </span>
        </Link>
      )}

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
              aria-label={
                to === '/cart' && showCartAffordance
                  ? `${label}: ${itemCount}`
                  : label
              }
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
              {to === '/cart' && showCartAffordance && (
                <span
                  aria-hidden="true"
                  className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[0.65rem] font-semibold leading-5 text-primary-foreground ring-2 ring-background"
                >
                  {cartBadge}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
