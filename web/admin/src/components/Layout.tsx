import { Outlet, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', key: 'dashboard' },
  { path: '/orders', key: 'orders' },
  { path: '/menu', key: 'menu' },
  { path: '/users', key: 'users' },
  { path: '/promos', key: 'promos' },
  { path: '/settings', key: 'settings' },
] as const;

export function Layout() {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 border-r bg-surface-muted p-4 hidden md:block">
        <div className="text-lg font-bold text-brand-700 mb-6">
          {t('appTitle')}
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.key}
              to={item.path}
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
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="border-b px-4 py-3 flex items-center justify-between">
          <span className="text-lg font-bold text-brand-700 md:hidden">
            {t('appTitle')}
          </span>
          <div className="ml-auto">
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
