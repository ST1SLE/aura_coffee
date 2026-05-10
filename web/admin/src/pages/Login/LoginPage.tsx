import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { staffLogin, setAccessToken, ApiError } from '@/api/client';
import { setRole, type StaffRole } from '@/lib/auth';
import { BrandMark, BrandWordmark } from '@/components/BrandMark';

// START_MODULE_CONTRACT
//   PURPOSE: Staff login form — login + password against /staff/auth/login.
//            On success stores the access token in module memory plus a role
//            hint, then navigates to returnUrl (or /, or /courier for couriers).
//   SCOPE:   Mounted at /login by App.tsx; the only unauthenticated page.
//   DEPENDS: react-router-dom, react-i18next, ui primitives, @/api/client,
//            @/lib/auth.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, AGENTS.md (login/password,
//            not SMS OTP), INV-002 (server validates credentials and issues role),
//            INV-010 (couriers always go to /courier regardless of returnUrl).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage - login form with submit handler that stores access+role and navigates
// END_MODULE_MAP

// START_CONTRACT: LoginPage
//   PURPOSE: Render staff login form, submit credentials to /staff/auth/login,
//            keep the access token in module memory, store a non-secret role
//            hint, rely on the server-set HttpOnly refresh cookie for rotation,
//            and navigate the user to the appropriate landing page (couriers
//            always go to /courier; others honour the returnUrl query param
//            or fall back to /).
//   INPUTS:  none (reads URL query via useSearchParams).
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: network POST via staffLogin; setAccessToken updates module
//            memory; setRole writes localStorage UX state; navigate() updates
//            browser history.
//   LINKS:   INV-002 (server is authoritative — bad credentials produce 401),
//            INV-010 (courier role hard-redirects to /courier — UX guard,
//            not security; even if a courier tampered with localStorage
//            the API would reject admin/barista calls).
// END_CONTRACT: LoginPage
export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const returnUrl = searchParams.get('returnUrl');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await staffLogin(login, password);
      setAccessToken(result.access_token);
      const role = result.role as StaffRole;
      setRole(role);
      // Курьер всегда попадает на /courier, returnUrl игнорируется (INV-010).
      const target = role === 'courier' ? '/courier' : (returnUrl ?? '/');
      navigate(target, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t('auth.login.invalidCredentials'));
      } else {
        setError(t('common.error'));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-sm rounded-lg border border-border/80 bg-card/95 p-6 shadow-[0_24px_80px_rgba(58,46,37,0.16)]">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <BrandWordmark
              decorative
              className="mb-3 h-8 w-auto max-w-[9.5rem] object-contain drop-shadow-[0_10px_18px_rgba(27,23,19,0.14)]"
            />
            <h1 className="text-2xl font-bold leading-tight">
              {t('auth.login.title')}
            </h1>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              {t('auth.login.subtitle')}
            </p>
          </div>
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_10px_24px_rgba(27,23,19,0.18)]">
            <BrandMark decorative tone="white" className="h-6 w-6 object-contain" />
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="login">{t('auth.login.loginLabel')}</Label>
            <Input
              id="login"
              type="text"
              placeholder={t('auth.login.loginPlaceholder')}
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              disabled={loading}
              autoComplete="username"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="password">{t('auth.login.passwordLabel')}</Label>
            <Input
              id="password"
              type="password"
              placeholder={t('auth.login.passwordPlaceholder')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full shadow-[0_14px_30px_rgba(58,46,37,0.12)]"
            disabled={!login || !password || loading}
          >
            <LogIn aria-hidden="true" />
            {loading ? t('auth.login.submitLoading') : t('auth.login.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
