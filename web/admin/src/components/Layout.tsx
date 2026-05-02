import { Outlet, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LogOut } from 'lucide-react';
import { logout } from '@/api/client';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { Button } from '@/components/ui/button';
import { useCurrentRole, type StaffRole } from '@/lib/auth';
import { cn } from '@/lib/utils';

// START_MODULE_CONTRACT
//   PURPOSE: Admin/barista shell layout — left sidebar nav whose visible items
//            are filtered by the current role hint, plus header with language
//            switcher, logout action, and a main outlet for nested routes.
//            Courier role uses CourierShell instead.
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
//   Layout - admin/barista shell with role-filtered sidebar nav and outlet
// END_MODULE_MAP

const navItems = [
  { path: '/', key: 'dashboard' },
  { path: '/orders', key: 'orders' },
  { path: '/menu', key: 'menu' },
  { path: '/users', key: 'users' },
  { path: '/promos', key: 'promos' },
  { path: '/settings', key: 'settings' },
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
//   PURPOSE: Render the admin/barista shell — sidebar nav (filtered by role) +
//            logout + header + Outlet for nested route content. Courier never
//            reaches this component (separate CourierShell tree).
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
        <div className="text-lg font-bold text-brand-700 mb-6">
          {t('appTitle')}
        </div>
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

      <div className="flex-1 flex flex-col">
        <header className="border-b px-4 py-3 flex items-center justify-between">
          <span className="text-lg font-bold text-brand-700 md:hidden">
            {t('appTitle')}
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

        <main className="flex-1 p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
