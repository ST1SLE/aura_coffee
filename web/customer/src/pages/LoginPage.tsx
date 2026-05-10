import { FormEvent, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PhoneInput, isValidPhone } from '@/components/auth/PhoneInput';
import { useAuth } from '@/auth/useAuth';
import { AuthError } from '@/api/auth';
import { Button } from '@/components/ui/button';
import { BrandWordmark } from '@/components/BrandMark';
import { warmCustomerMenuMedia } from '@/media/menuWarmup';

// START_MODULE_CONTRACT
//   PURPOSE: /login route — phone entry step of the OTP flow. Validates with
//            isValidPhone before enabling submit, calls AuthProvider.login
//            (sendCode), then navigates to /login/verify with both `phone` and
//            the original `returnUrl` carried via location.state.
//   SCOPE:   LoginPage component.
//   DEPENDS: react, react-router-dom, react-i18next, @/components/auth/PhoneInput,
//            @/auth/useAuth, @/api/auth (AuthError), @/components/ui/button,
//            @/media/menuWarmup.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6.1 send-code;
//            INV-013 — phone is PII; do not log raw values.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   LoginPage  - /login route — phone entry + send-code submission
// END_MODULE_MAP

// START_CONTRACT: LoginPage
//   PURPOSE: Render the phone form, call sendCode through useAuth, route to
//            /login/verify with phone + returnUrl on success, or render a
//            localized error on AuthError (RATE_LIMITED vs network/unknown).
//   INPUTS:  none.
//   OUTPUTS: JSX — phone form with error/loading state.
//   SIDE_EFFECTS: useAuth().login (HTTP POST /auth/send-code via api/auth);
//                 starts bounded menu media warmup; navigate('/login/verify')
//                 on success. INV-013 PII handling.
//   LINKS:   PDD §6.1; pairs with VerifyPage.
// END_CONTRACT: LoginPage
export function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const returnUrl = (location.state as { returnUrl?: string })?.returnUrl;
  const [phone, setPhone] = useState('+7');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = isValidPhone(phone);
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';

  useEffect(() => {
    warmCustomerMenuMedia(lang);
  }, [lang]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid || isSubmitting) return;

    setError(null);
    setIsSubmitting(true);
    try {
      await login(phone);
      navigate('/login/verify', { state: { phone, returnUrl } });
    } catch (err) {
      if (err instanceof AuthError) {
        if (err.code === 'RATE_LIMITED') {
          setError(t('auth.otp.error.rateLimit'));
        } else {
          setError(t('auth.otp.error.network'));
        }
      } else {
        setError(t('auth.otp.error.network'));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="aura-surface w-full max-w-sm overflow-hidden rounded-lg bg-card/95">
        <div className="border-b border-border/60 bg-muted/75 px-5 py-6 text-center">
          <BrandWordmark
            alt={t('appTitle')}
            className="mx-auto mb-3 h-8 w-auto max-w-[9.5rem] object-contain drop-shadow-[0_10px_18px_rgba(27,23,19,0.12)]"
          />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <PhoneInput
            value={phone}
            onChange={setPhone}
            disabled={isSubmitting}
          />

          {error && (
            <p className="text-center text-sm text-destructive">{error}</p>
          )}

          <Button
            type="submit"
            disabled={!valid || isSubmitting}
            className="w-full"
          >
            {isSubmitting ? t('auth.phone.submitting') : t('auth.phone.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
