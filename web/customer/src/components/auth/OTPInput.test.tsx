import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OTPInput } from './OTPInput';

describe('OTPInput', () => {
  it('renders 6 input fields', () => {
    render(<OTPInput value="" onChange={() => {}} onComplete={() => {}} />);
    const inputs = screen.getAllByRole('textbox');
    expect(inputs).toHaveLength(6);
  });

  it('calls onChange on digit entry', () => {
    const onChange = vi.fn();
    render(<OTPInput value="" onChange={onChange} onComplete={() => {}} />);
    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: '1' } });
    expect(onChange).toHaveBeenCalled();
  });

  it('calls onComplete when all 6 digits entered', () => {
    const onComplete = vi.fn();
    const onChange = vi.fn();
    render(<OTPInput value="00000" onChange={onChange} onComplete={onComplete} />);
    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[5], { target: { value: '0' } });
    expect(onComplete).toHaveBeenCalledWith('000000');
  });

  it('handles paste of 6 digits', () => {
    const onComplete = vi.fn();
    const onChange = vi.fn();
    render(<OTPInput value="" onChange={onChange} onComplete={onComplete} />);
    const inputs = screen.getAllByRole('textbox');
    fireEvent.paste(inputs[0], {
      clipboardData: { getData: () => '123456' },
    });
    expect(onComplete).toHaveBeenCalledWith('123456');
  });

  it('handles backspace on empty field', () => {
    const onChange = vi.fn();
    render(<OTPInput value="12    " onChange={onChange} onComplete={() => {}} />);
    const inputs = screen.getAllByRole('textbox');
    fireEvent.keyDown(inputs[2], { key: 'Backspace' });
    expect(onChange).toHaveBeenCalled();
  });

  it('disables all inputs when disabled', () => {
    render(<OTPInput value="" onChange={() => {}} onComplete={() => {}} disabled />);
    const inputs = screen.getAllByRole('textbox');
    inputs.forEach((input) => {
      expect(input).toHaveProperty('disabled', true);
    });
  });
});
