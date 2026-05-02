import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// START_MODULE_CONTRACT
//   PURPOSE: Resend-OTP cooldown widget — shows "Resend in N s" while a 60s
//            timer ticks down, then turns into a Resend button. On click
//            invokes onResend and restarts the cooldown.
//   SCOPE:   ResendTimer component.
//   DEPENDS: react, react-i18next, @/components/ui/button.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6.2 resend.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   ResendTimer  - 60s cooldown with text label + button toggle
// END_MODULE_MAP

const RESEND_DELAY = 60;

interface ResendTimerProps {
  onResend: () => void;
  disabled?: boolean;
}

// START_CONTRACT: ResendTimer
//   PURPOSE: Render a 60-second resend cooldown that flips into a button.
//   INPUTS:  ResendTimerProps — onResend: () => void, disabled?: boolean.
//   OUTPUTS: JSX — countdown <p> while ticking, Button after.
//   SIDE_EFFECTS: setInterval/clearInterval (1s); calls onResend on click and
//                 resets the local cooldown.
//   LINKS:   PDD §6.2; consumed by VerifyPage.
// END_CONTRACT: ResendTimer
export function ResendTimer({ onResend, disabled }: ResendTimerProps) {
  const { t } = useTranslation();
  const [secondsLeft, setSecondsLeft] = useState(RESEND_DELAY);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setInterval(() => {
      setSecondsLeft((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsLeft]);

  const handleResend = useCallback(() => {
    onResend();
    setSecondsLeft(RESEND_DELAY);
  }, [onResend]);

  if (secondsLeft > 0) {
    return (
      <p className="text-center text-sm text-muted-foreground">
        {t('auth.otp.resendIn', { seconds: secondsLeft })}
      </p>
    );
  }

  return (
    <Button
      variant="ghost"
      onClick={handleResend}
      disabled={disabled}
      className="w-full"
    >
      {t('auth.otp.resend')}
    </Button>
  );
}
