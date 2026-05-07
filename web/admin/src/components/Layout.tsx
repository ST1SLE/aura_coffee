import { Outlet, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ClipboardList,
  Coffee,
  LayoutDashboard,
  LogOut,
  Settings,
  TicketPercent,
  Users,
} from 'lucide-react';
import { logout } from '@/api/client';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { BrandMark, BrandWordmark } from '@/components/BrandMark';
import { Button } from '@/components/ui/button';
import { useCurrentRole, type StaffRole } from '@/lib/auth';
import { cn } from '@/lib/utils';

// START_MODULE_CONTRACT
//   PURPOSE: Admin/barista shell layout — left sidebar nav whose visible items
//            are filtered by the current role hint, a matching mobile bottom
//            nav for small screens, plus header with language switcher, logout
//            action, and a main outlet for nested routes. Courier role uses
//            CourierShell instead.
//   SCOPE:   Mounted under the admin/barista ProtectedRoute branch in App.tsx.
//   DEPENDS: react-router-dom (Outlet/Link/useLocation), react-i18next,
//            lucide-react, @/api/client, @/components/LanguageSwitcher,
//            @/components/BrandMark, @/components/ui/button, @/lib/auth,
//            @/lib/utils.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (role isolation),
//            INV-002, INV-010.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   Layout - admin/barista shell with role-filtered desktop/mobile nav and outlet
// END_MODULE_MAP

const navItems = [
  { path: '/', key: 'dashboard', icon: LayoutDashboard },
  { path: '/orders', key: 'orders', icon: ClipboardList },
  { path: '/menu', key: 'menu', icon: Coffee },
  { path: '/users', key: 'users', icon: Users },
  { path: '/promos', key: 'promos', icon: TicketPercent },
  { path: '/settings', key: 'settings', icon: Settings },
] as const;

// Exhaustive по StaffRole: добавление новой роли в union без обновления
// этого объекта даст compile-time ошибку.
const NAV_BY_ROLE: Record<StaffRole, readonly string[]> = {
  admin: ['dashboard', 'orders', 'menu', 'users', 'promos', 'settings'],
  barista: ['orders', 'menu'],
  // У courier'а собственный CourierShell; defensive default на случай
  // edge-case попадания в Layout-tree.
  courier: [],
};

// START_CONTRACT: Layout
//   PURPOSE: Render the admin/barista shell — desktop sidebar nav and mobile
//            bottom nav (both filtered by role) + logout + header + Outlet for
//            nested route content. Courier never reaches this component
//            (separate CourierShell tree).
//   INPUTS:  none (uses router/i18n/role hooks).
//   OUTPUTS: JSX.Element
//   SIDE_EFFECTS: reads useCurrentRole / useLocation / useTranslation; Link
//            navigation updates router state; logout clears staff auth state
//            and navigates to /admin/login via api/client.logout.
//   LINKS:   INV-002 (server enforces auth/role; this filter is UX only),
//            INV-010 (role isolation — barista nav has only orders+menu).
// END_CONTRACT: Layout
export function Layout() {
  const { t } = useTranslation();
  const location = useLocation();
  const role = useCurrentRole();
  const allowedKeys = role ? NAV_BY_ROLE[role] : [];
  const visibleItems = navItems.filter((i) => allowedKeys.includes(i.key));

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 border-r border-white/10 bg-[hsl(var(--admin-sidebar))] text-[hsl(var(--admin-sidebar-foreground))] md:flex md:flex-col">
        <div className="border-b border-white/10 px-5 py-5">
          <Link
            to="/"
            className="flex min-w-0 items-center gap-3"
            aria-label={t('appTitle')}
          >
            <BrandMark
              decorative
              tone="white"
              className="h-10 w-10 shrink-0 object-contain drop-shadow-[0_10px_18px_rgba(0,0,0,0.18)]"
            />
            <span className="min-w-0 space-y-1">
              <BrandWordmark
                decorative
                tone="white"
                className="h-5 w-auto max-w-[7.5rem] object-contain"
              />
              <span className="block truncate text-xs font-semibold text-white/70">
                {t('appTitle')}
              </span>
            </span>
          </Link>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.key}
                to={item.path}
                data-testid={`nav-${item.key}`}
                className={cn(
                  'flex min-h-10 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-white/10 text-white shadow-[inset_3px_0_0_hsl(var(--accent))]'
                    : 'text-white/70 hover:bg-white/10 hover:text-white',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{t(`nav.${item.key}`)}</span>
              </Link>
            );
          })}
        </nav>
        <Button
          type="button"
          variant="ghost"
          data-testid="logout-sidebar"
          className="mx-3 mb-4 w-[calc(100%-1.5rem)] justify-start text-white/70 hover:bg-white/10 hover:text-white"
          onClick={logout}
        >
          <LogOut aria-hidden="true" />
          {t('nav.logout')}
        </Button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border/80 bg-background/95 px-4 py-3 backdrop-blur md:px-6">
          <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-primary md:hidden">
            <BrandMark
              decorative
              className="h-8 w-8 shrink-0 object-contain"
            />
            <BrandWordmark
              decorative
              className="h-4 w-auto max-w-[6.5rem] object-contain"
            />
            <span className="sr-only">{t('appTitle')}</span>
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="logout-mobile"
              className="md:hidden"
              onClick={logout}
            >
              <LogOut aria-hidden="true" />
              {t('nav.logout')}
            </Button>
            <LanguageSwitcher />
          </div>
        </header>

        {visibleItems.length > 0 && (
          <nav
            aria-label={t('nav.mobileLabel')}
            data-testid="mobile-nav"
            className="sticky top-[57px] z-20 border-b border-border/80 bg-card/95 px-2 py-2 shadow-[0_8px_24px_rgba(26,37,33,0.08)] backdrop-blur md:hidden"
          >
            <div className="flex gap-1 overflow-x-auto">
              {visibleItems.map((item) => {
                const Icon = item.icon;
                const active = location.pathname === item.path;
                return (
                  <Link
                    key={item.key}
                    to={item.path}
                    data-testid={`nav-mobile-${item.key}`}
                    className={cn(
                      'flex h-14 min-w-[4.75rem] flex-1 flex-col items-center justify-center rounded-md px-2 py-1.5 text-center text-[10px] font-medium leading-tight transition-colors',
                      active
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'text-muted-foreground hover:bg-secondary hover:text-secondary-foreground',
                    )}
                  >
                    <Icon className="mb-0.5 h-4 w-4" aria-hidden="true" />
                    <span className="max-w-full whitespace-normal break-words leading-tight">
                      {t(`nav.${item.key}`)}
                    </span>
                  </Link>
                );
              })}
            </div>
          </nav>
        )}

        <main className="min-w-0 flex-1 px-4 py-5 pb-6 sm:px-6 md:pb-8 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
