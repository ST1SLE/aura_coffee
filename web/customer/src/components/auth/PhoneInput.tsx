import { useCallback, useState } from 'react';

// START_MODULE_CONTRACT
//   PURPOSE: Russian-format phone input — locks the country code to +7,
//            formats the 10 trailing digits as `(NNN) NNN-NN-NN` while typing,
//            and emits a normalized `+7XXXXXXXXXX` string via onChange.
//            Also exports a small validator used by LoginPage to enable submit.
//   SCOPE:   PhoneInput component + isValidPhone validator.
//   DEPENDS: react (useCallback, useState).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6.1 send-code.
//            INV-013 — phone is PII; component does not log raw values.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   PhoneInput     - controlled phone input with mask and onChange normalization
//   isValidPhone   - test that a normalized string matches +7\d{10}
// END_MODULE_MAP

interface PhoneInputProps {
  value: string;
  onChange: (normalized: string) => void;
  disabled?: boolean;
}

function formatDisplay(digits: string): string {
  const d = digits.slice(0, 10);
  if (d.length === 0) return '';
  if (d.length <= 3) return `(${d}`;
  if (d.length <= 6) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
  if (d.length <= 8) return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6, 8)}-${d.slice(8)}`;
}

function extractDigits(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 10);
}

// START_CONTRACT: PhoneInput
//   PURPOSE: Render a phone input with a static "+7" prefix and a digit-mask
//            for the 10 user digits.
//   INPUTS:  PhoneInputProps — value: string ('+7'+digits), onChange:
//            (normalized) => void, disabled?: boolean.
//   OUTPUTS: JSX — span("+7") + masked <input type="tel">.
//   SIDE_EFFECTS: parent state via onChange. INV-013 — do not log raw value.
//   LINKS:   PDD §6.1; consumed by LoginPage; pairs with isValidPhone.
// END_CONTRACT: PhoneInput
export function PhoneInput({ value, onChange, disabled }: PhoneInputProps) {
  const digits = value.startsWith('+7') ? value.slice(2) : '';
  const [displayValue, setDisplayValue] = useState(formatDisplay(digits));

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      const newDigits = extractDigits(raw);
      setDisplayValue(formatDisplay(newDigits));
      onChange(`+7${newDigits}`);
    },
    [onChange],
  );

  return (
    <div className="flex items-center gap-2">
      <span className="font-display text-lg font-semibold text-foreground">+7</span>
      <input
        type="tel"
        inputMode="numeric"
        value={displayValue}
        onChange={handleChange}
        disabled={disabled}
        placeholder="(999) 123-45-67"
        className="flex-1 rounded-lg border border-input bg-card px-3 py-2 text-lg text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
        autoComplete="tel-national"
      />
    </div>
  );
}

// START_CONTRACT: isValidPhone
//   PURPOSE: Verify a normalized phone string is exactly "+7" + 10 digits.
//   INPUTS:  normalized: string — the value emitted by PhoneInput.onChange.
//   OUTPUTS: boolean.
//   SIDE_EFFECTS: none.
// END_CONTRACT: isValidPhone
export function isValidPhone(normalized: string): boolean {
  return /^\+7\d{10}$/.test(normalized);
}
