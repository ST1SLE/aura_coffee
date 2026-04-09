import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

const RESEND_DELAY = 60;

interface ResendTimerProps {
  onResend: () => void;
  disabled?: boolean;
}

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
      <p className="text-center text-sm text-gray-500">
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
