import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PhoneInput, isValidPhone } from './PhoneInput';

describe('PhoneInput', () => {
  it('renders with +7 prefix', () => {
    render(<PhoneInput value="+7" onChange={() => {}} />);
    expect(screen.getByText('+7')).toBeDefined();
  });

  it('formats input as (XXX) XXX-XX-XX', () => {
    const onChange = vi.fn();
    render(<PhoneInput value="+7" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '9991234567' } });
    expect(onChange).toHaveBeenCalledWith('+79991234567');
  });

  it('strips non-digit characters', () => {
    const onChange = vi.fn();
    render(<PhoneInput value="+7" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '(999) 123' } });
    expect(onChange).toHaveBeenCalledWith('+7999123');
  });

  it('limits to 10 digits', () => {
    const onChange = vi.fn();
    render(<PhoneInput value="+7" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '99912345678999' } });
    expect(onChange).toHaveBeenCalledWith('+79991234567');
  });
});

describe('isValidPhone', () => {
  it('returns true for valid E.164 phone', () => {
    expect(isValidPhone('+79991234567')).toBe(true);
  });

  it('returns false for short phone', () => {
    expect(isValidPhone('+7999123')).toBe(false);
  });

  it('returns false for empty', () => {
    expect(isValidPhone('+7')).toBe(false);
  });
});
