import { Outlet, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

export function Layout() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <Link to="/" className="text-lg font-bold text-brand-700">
          {t('appTitle')}
        </Link>
        <LanguageSwitcher />
      </header>

      <main className="flex-1 p-4">
        <Outlet />
      </main>

      <nav className="border-t px-4 py-2 flex justify-around md:hidden">
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
      </nav>
    </div>
  );
}
