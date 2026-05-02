import { useCallback, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { OTPInput } from '@/components/auth/OTPInput';
import { ResendTimer } from '@/components/auth/ResendTimer';
import { useAuth } from '@/auth/useAuth';
import { AuthError } from '@/api/auth';

// START_MODULE_CONTRACT
//   PURPOSE: /login/verify route — OTP entry step. Reads phone + returnUrl
//            from location.state (redirects to /login if missing), submits
//            the code through useAuth.verifyCode, then navigates to the
//            preserved returnUrl (or /). Maps AuthError codes to localized
//            error strings and supports OTP resend via ResendTimer.
//   SCOPE:   VerifyPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/components/auth/OTPInput,
//            @/components/auth/ResendTimer, @/auth/useAuth, @/api/auth (AuthError).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6.2 verify-code;
//            INV-013 (phone is PII — only displayed masked in this UI).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VerifyPage  - /login/verify — OTP entry + resend + error mapping
// END_MODULE_MAP

function maskPhone(phone: string): string {
  if (phone.length < 6) return phone;
  return phone.slice(0, 4) + '***' + phone.slice(-2);
}

// START_CONTRACT: VerifyPage
//   PURPOSE: Render the OTP entry screen and complete the OTP flow on success.
//   INPUTS:  none (reads location.state.phone + returnUrl).
//   OUTPUTS: JSX — masked phone label, OTPInput, error text, ResendTimer; or
//            <Navigate to="/login"> when no phone is present in state.
//   SIDE_EFFECTS: useAuth().verifyCode (HTTP POST /auth/verify-code, sets
//                 tokens + user); useAuth().login on resend (HTTP POST
//                 /auth/send-code); navigate(returnUrl, { replace: true }) on
//                 success. INV-013 — phone shown masked only.
//   LINKS:   PDD §6.2; pairs with LoginPage and OTPInput.
// END_CONTRACT: VerifyPage
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
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="aura-surface w-full max-w-sm space-y-6 rounded-lg p-5">
        <div className="space-y-2 text-center">
          <h1 className="font-display text-2xl font-bold">{t('auth.otp.title')}</h1>
          <p className="text-sm text-muted-foreground">{maskPhone(phone)}</p>
        </div>

        <OTPInput
          value={code}
          onChange={setCode}
          onComplete={handleComplete}
          disabled={isSubmitting}
        />

        {error && (
          <p className="text-center text-sm text-destructive">{error}</p>
        )}

        <ResendTimer onResend={handleResend} disabled={isSubmitting} />
      </div>
    </div>
  );
}
