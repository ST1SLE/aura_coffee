import { useCallback, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { OTPInput } from '@/components/auth/OTPInput';
import { ResendTimer } from '@/components/auth/ResendTimer';
import { useAuth } from '@/auth/useAuth';
import { AuthError } from '@/api/auth';

function maskPhone(phone: string): string {
  if (phone.length < 6) return phone;
  return phone.slice(0, 4) + '***' + phone.slice(-2);
}

export function VerifyPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { verifyCode, login } = useAuth();

  const phone = (location.state as { phone?: string })?.phone;
  const returnUrl = (location.state as { returnUrl?: string })?.returnUrl || '/';

  const [code, setCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleComplete = useCallback(
    async (submittedCode: string) => {
      if (isSubmitting || !phone) return;

      setError(null);
      setIsSubmitting(true);
      try {
        await verifyCode(phone, submittedCode);
        navigate(returnUrl, { replace: true });
      } catch (err) {
        if (err instanceof AuthError) {
          switch (err.code) {
            case 'INVALID_CODE':
              setError(t('auth.otp.error.invalid'));
              break;
            case 'CODE_EXPIRED':
              setError(t('auth.otp.error.expired'));
              break;
            case 'CODE_NOT_DELIVERED':
              setError(t('auth.otp.error.notDelivered'));
              break;
            case 'RATE_LIMITED':
              setError(t('auth.otp.error.rateLimit'));
              break;
            default:
              setError(t('auth.otp.error.network'));
          }
        } else {
          setError(t('auth.otp.error.network'));
        }
        setCode('');
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, phone, verifyCode, navigate, returnUrl, t],
  );

  const handleResend = useCallback(async () => {
    if (!phone) return;
    try {
      await login(phone);
      setError(null);
    } catch {
      setError(t('auth.otp.error.network'));
    }
  }, [phone, login, t]);

  if (!phone) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">{t('auth.otp.title')}</h1>
          <p className="text-sm text-gray-500">{maskPhone(phone)}</p>
        </div>

        <OTPInput
          value={code}
          onChange={setCode}
          onComplete={handleComplete}
          disabled={isSubmitting}
        />

        {error && (
          <p className="text-center text-sm text-red-600">{error}</p>
        )}

        <ResendTimer onResend={handleResend} disabled={isSubmitting} />
      </div>
    </div>
  );
}
