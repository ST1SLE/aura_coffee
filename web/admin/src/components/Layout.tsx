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
import { BrandMark } from '@/components/BrandMark';
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
//            @/components/ui/button, @/lib/auth, @/lib/utils.
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
    <div className="min-h-screen flex">
      <aside className="w-56 border-r bg-surface-muted p-4 hidden md:flex md:flex-col">
        <Link
          to="/"
          className="mb-6 flex min-w-0 items-center gap-3 text-lg font-bold text-brand-700"
          aria-label={t('appTitle')}
        >
          <BrandMark
            decorative
            className="h-10 w-12 shrink-0 rounded-md object-cover shadow-sm"
          />
          <span className="truncate">{t('appTitle')}</span>
        </Link>
        <nav className="space-y-1 flex-1">
          {visibleItems.map((item) => (
            <Link
              key={item.key}
              to={item.path}
              data-testid={`nav-${item.key}`}
              className={cn(
                'block rounded-md px-3 py-2 text-sm transition-colors',
                location.pathname === item.path
                  ? 'bg-brand-100 text-brand-900 font-medium'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              {t(`nav.${item.key}`)}
            </Link>
          ))}
        </nav>
        <Button
          type="button"
          variant="ghost"
          data-testid="logout-sidebar"
          className="mt-4 w-full justify-start text-muted-foreground hover:text-foreground"
          onClick={logout}
        >
          <LogOut aria-hidden="true" />
          {t('nav.logout')}
        </Button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b px-4 py-3 flex items-center justify-between">
          <span className="flex min-w-0 items-center gap-2 text-lg font-bold text-brand-700 md:hidden">
            <BrandMark
              decorative
              className="h-7 w-8 shrink-0 rounded-md object-cover"
            />
            <span className="truncate">{t('appTitle')}</span>
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

        <main className="min-w-0 flex-1 p-4 pb-24 md:pb-4">
          <Outlet />
        </main>
      </div>

      {visibleItems.length > 0 && (
        <nav
          aria-label={t('nav.mobileLabel')}
          data-testid="mobile-nav"
          className="fixed inset-x-0 bottom-0 z-40 border-t bg-background px-2 py-2 shadow-[0_-4px_12px_rgba(0,0,0,0.06)] md:hidden"
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
                    'flex min-w-[4.5rem] flex-1 flex-col items-center justify-center rounded-md px-2 py-1.5 text-center text-[11px] leading-tight transition-colors',
                    active
                      ? 'bg-brand-100 text-brand-900 font-medium'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                >
                  <Icon className="mb-0.5 h-4 w-4" aria-hidden="true" />
                  <span className="max-w-full truncate">
                    {t(`nav.${item.key}`)}
                  </span>
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}
