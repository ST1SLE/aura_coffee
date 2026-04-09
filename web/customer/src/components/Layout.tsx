import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useAuth } from '@/auth/useAuth';

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
