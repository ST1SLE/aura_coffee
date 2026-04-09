import { useCallback, useState } from 'react';

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
      <span className="text-lg font-medium text-gray-700">+7</span>
      <input
        type="tel"
        inputMode="numeric"
        value={displayValue}
        onChange={handleChange}
        disabled={disabled}
        placeholder="(999) 123-45-67"
        className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-lg focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900 disabled:opacity-50"
        autoComplete="tel-national"
      />
    </div>
  );
}

export function isValidPhone(normalized: string): boolean {
  return /^\+7\d{10}$/.test(normalized);
}
