import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  staffLogin,
  setAccessToken,
  ApiError,
} from '@/api/client';
import { setRole, type StaffRole } from '@/lib/auth';
import { BrandMark } from '@/components/BrandMark';

// START_MODULE_CONTRACT
//   PURPOSE: Staff login form — login + password against /staff/auth/login.
//            On success stores the access token + role hint, then navigates to
//            returnUrl (or /, or /courier for couriers).
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
//            store access token + role hint on success, rely on the server-set
//            HttpOnly refresh cookie for rotation, and navigate the user to the
//            appropriate landing page (couriers
//            always go to /courier; others honour the returnUrl query param
//            or fall back to /).
//   INPUTS:  none (reads URL query via useSearchParams).
//   OUTPUTS: JSX.Element.
//   SIDE_EFFECTS: network POST via staffLogin; setAccessToken/setRole writes
//            localStorage UX state; navigate() updates browser history.
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
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6 p-6">
        <div>
          <BrandMark
            decorative
            className="mb-3 h-11 w-12 rounded-md object-cover shadow-sm"
          />
          <h1 className="text-2xl font-bold">{t('auth.login.title')}</h1>
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
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={!login || !password || loading}
          >
            {loading ? t('auth.login.submitLoading') : t('auth.login.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
