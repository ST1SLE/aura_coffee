import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';

// START_MODULE_CONTRACT
//   PURPOSE: 6-digit OTP input — six single-character inputs that auto-advance,
//            handle Backspace (clear current then move back), accept paste of
//            the full code, and fire onComplete when all six digits are filled.
//   SCOPE:   OTPInput component.
//   DEPENDS: react (useCallback, useRef), react-i18next.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6.2 verify-code.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   OTPInput  - controlled 6-digit OTP input with auto-advance and paste support
// END_MODULE_MAP

const CODE_LENGTH = 6;

interface OTPInputProps {
  value: string;
  onChange: (code: string) => void;
  onComplete: (code: string) => void;
  disabled?: boolean;
}

// START_CONTRACT: OTPInput
//   PURPOSE: Controlled 6-digit code entry — emits onChange on every edit and
//            onComplete exactly when the value becomes a valid 6-digit string.
//   INPUTS:  OTPInputProps — value: string, onChange: (code) => void,
//            onComplete: (code) => void, disabled?: boolean.
//   OUTPUTS: JSX — six <input maxLength=1> with shared keyboard/paste behavior.
//   SIDE_EFFECTS: focus(), parent state via callbacks. INV-013 — code is short-
//                 lived auth secret, do not log.
//   LINKS:   PDD §6.2; consumed by VerifyPage.
// END_CONTRACT: OTPInput
export function OTPInput({ value, onChange, onComplete, disabled }: OTPInputProps) {
  const { t } = useTranslation();
  const inputsRef = useRef<(HTMLInputElement | null)[]>([]);
  const digits = value.padEnd(CODE_LENGTH, ' ').slice(0, CODE_LENGTH).split('');

  const focusInput = (index: number) => {
    inputsRef.current[index]?.focus();
  };

  const updateCode = useCallback(
    (newDigits: string[]) => {
      const code = newDigits.join('');
      onChange(code);
      if (code.length === CODE_LENGTH && !code.includes(' ') && /^\d{6}$/.test(code)) {
        onComplete(code);
      }
    },
    [onChange, onComplete],
  );

  const handleInput = useCallback(
    (index: number, char: string) => {
      if (!/^\d$/.test(char)) return;
      const newDigits = [...digits];
      newDigits[index] = char;
      updateCode(newDigits);
      if (index < CODE_LENGTH - 1) {
        focusInput(index + 1);
      }
    },
    [digits, updateCode],
  );

  const handleKeyDown = useCallback(
    (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Backspace') {
        e.preventDefault();
        const newDigits = [...digits];
        if (digits[index] && digits[index] !== ' ') {
          newDigits[index] = ' ';
          updateCode(newDigits);
        } else if (index > 0) {
          newDigits[index - 1] = ' ';
          updateCode(newDigits);
          focusInput(index - 1);
        }
      }
    },
    [digits, updateCode],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      e.preventDefault();
      const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, CODE_LENGTH);
      if (pasted.length === 0) return;
      const newDigits = pasted.padEnd(CODE_LENGTH, ' ').split('');
      updateCode(newDigits);
      focusInput(Math.min(pasted.length, CODE_LENGTH - 1));
    },
    [updateCode],
  );

  return (
    <div className="flex justify-center gap-2">
      {digits.map((digit, i) => (
        <input
          key={i}
          ref={(el) => { inputsRef.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={digit === ' ' ? '' : digit}
          disabled={disabled}
          onChange={(e) => handleInput(i, e.target.value.slice(-1))}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          aria-label={t('auth.otp.digitLabel', {
            position: i + 1,
            total: CODE_LENGTH,
          })}
          className="h-12 w-12 rounded-lg border border-input bg-card text-center font-display text-xl font-semibold text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
        />
      ))}
    </div>
  );
}
