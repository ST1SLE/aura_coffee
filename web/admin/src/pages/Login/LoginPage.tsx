import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { staffLogin, setAccessToken, ApiError } from '@/api/client';
import { setRole, type StaffRole } from '@/lib/auth';

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
        <h1 className="text-2xl font-bold">{t('auth.login.title')}</h1>

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
