import { useEffect } from 'react';
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
import { BrandMark, BrandWordmark } from '@/components/BrandMark';
import { useAuth } from '@/auth/useAuth';
import { useCartStore } from '@/store/cart';
import { formatPrice } from '@/lib/formatPrice';

// START_MODULE_CONTRACT
//   PURPOSE: Soft botanical mobile-first app shell — sticky brand/ordering
//            header with nav links + logout + LanguageSwitcher, the <main>
//            outlet, mobile bottom nav, and cart-count/cart-total affordances
//            when the cart has items. Refreshes cart state after auth is
//            resolved so the browsing menu exposes an existing cart after
//            reload.
//   SCOPE:   Layout component.
//   DEPENDS: react-router-dom (Outlet/Link/NavLink/useLocation/useNavigate),
//            react-i18next, lucide-react, @/components/LanguageSwitcher,
//            @/components/BrandMark,
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
//            Cart links include count labels/badges when itemCount > 0; the
//            menu route also shows a bottom cart-total bar.
//   SIDE_EFFECTS: handleLogout calls useAuth().logout (which clears tokens +
//                 calls /auth/logout) then navigates to /login.
//                 After auth resolves, refreshes idle cart state through
//                 GET /cart via the cart store.
//                 INV-002 — server enforces auth; this nav is UX only.
//   LINKS:   App.tsx wraps protected routes with this layout.
// END_CONTRACT: Layout
export function Layout() {
  const { t, i18n } = useTranslation();
  const { logout, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const itemCount = useCartStore((state) => state.itemCount);
  const subtotal = useCartStore((state) => state.subtotal);
  const cartStatus = useCartStore((state) => state.status);
  const refreshCart = useCartStore((state) => state.refresh);
  const cartBadge = itemCount > 99 ? '99+' : String(itemCount);
  const cartTotal = formatPrice(subtotal, i18n.language === 'ru' ? 'ru' : 'en');
  const showCartAffordance = itemCount > 0;
  const showFloatingCart =
    showCartAffordance &&
    (location.pathname === '/menu' || location.pathname.startsWith('/menu/'));

  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    if (cartStatus !== 'idle') return;
    void refreshCart().catch(() => undefined);
  }, [cartStatus, isAuthenticated, isLoading, refreshCart]);

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
      <header className="sticky top-0 z-40 border-b border-border/70 bg-card/95 px-4 py-2.5 shadow-[0_10px_30px_rgba(58,46,37,0.12)] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3">
          <Link
            to="/menu"
            className="flex min-w-0 items-center gap-3 text-base font-semibold tracking-normal text-card-foreground"
          >
            <BrandMark
              decorative
              className="h-10 w-10 shrink-0 object-contain drop-shadow-[0_8px_16px_rgba(58,46,37,0.14)]"
            />
            <span className="min-w-0">
              <BrandWordmark
                alt={t('appTitle')}
                className="h-5 w-auto max-w-[7.5rem] object-contain sm:h-6 sm:max-w-[8.5rem]"
              />
              <span className="block max-w-[10.5rem] truncate text-xs font-normal text-muted-foreground sm:max-w-[12rem]">
                {t('pages.home.headerTagline')}
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
                    'font-display relative inline-flex h-11 min-w-11 items-center gap-2 rounded-md px-3 text-sm font-semibold transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-[0_8px_18px_rgba(108,122,85,0.16)]'
                      : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground',
                  ].join(' ')
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
                {to === '/cart' && showCartAffordance && (
                  <span
                    aria-hidden="true"
                    className="ml-0.5 inline-flex min-w-5 items-center justify-center rounded-full bg-card px-1.5 text-[0.68rem] font-semibold leading-5 text-primary"
                  >
                    {cartBadge}
                  </span>
                )}
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="font-display inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-semibold text-muted-foreground transition-colors hover:bg-secondary hover:text-secondary-foreground"
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

      <main
        className={[
          'mx-auto w-full max-w-6xl flex-1',
          showFloatingCart ? 'pb-40 md:pb-28' : 'pb-28 md:pb-10',
        ].join(' ')}
      >
        <Outlet />
      </main>

      {showFloatingCart && (
        <Link
          to="/cart"
          aria-label={`${t('nav.cart')}: ${itemCount}`}
          className="font-display fixed bottom-[calc(5.25rem+env(safe-area-inset-bottom))] left-4 right-4 z-50 mx-auto inline-flex min-h-14 max-w-sm items-center justify-between gap-3 rounded-full border border-primary-foreground/15 bg-foreground px-3 py-2 text-sm font-semibold text-primary-foreground shadow-[0_18px_42px_rgba(30,24,19,0.34)] backdrop-blur-xl transition-colors hover:bg-foreground/95 md:bottom-6 md:max-w-md"
          data-testid="floating-cart-link"
        >
          <span className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <ShoppingBag className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="min-w-0 text-left">
              <span className="block truncate">{t('nav.cart')}</span>
              <span className="aura-numeric block truncate text-xs font-medium text-primary-foreground/75">
                {cartTotal}
              </span>
            </span>
          </span>
          <span
            aria-hidden="true"
            className="inline-flex min-w-7 items-center justify-center rounded-full bg-card/90 px-2 text-xs font-semibold leading-7 text-foreground"
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
        <div className="relative mx-auto h-14 max-w-sm rounded-full border border-border/80 bg-card/95 shadow-[0_-12px_34px_rgba(58,46,37,0.16)] backdrop-blur-xl">
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
                    ? 'bg-primary text-primary-foreground shadow-[0_8px_16px_rgba(108,122,85,0.16)]'
                    : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground',
                ].join(' ')
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {to === '/cart' && showCartAffordance && (
                <span
                  aria-hidden="true"
                  className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[0.65rem] font-semibold leading-5 text-primary-foreground ring-2 ring-card"
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
