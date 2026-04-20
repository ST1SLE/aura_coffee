import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionTiming } from './SectionTiming';
import { validateTiming } from './validation';
import { baseForm } from './testUtils';

describe('SectionTiming', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('рендерит 3 поля', () => {
    render(<SectionTiming form={baseForm()} onChange={() => {}} errors={{}} />);
    expect(screen.getByLabelText(/Preparation time/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Delivery time/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Pickup auto-close/i)).toBeInTheDocument();
  });

  it('auto_close_minutes=0 → error', () => {
    expect(
      validateTiming({ ...baseForm(), auto_close_minutes: '0' }).auto_close_minutes,
    ).toBe('out_of_range');
  });

  it('auto_close_minutes=1441 → error', () => {
    expect(
      validateTiming({ ...baseForm(), auto_close_minutes: '1441' }).auto_close_minutes,
    ).toBe('out_of_range');
  });

  it('auto_close_minutes=60 → OK', () => {
    expect(validateTiming({ ...baseForm(), auto_close_minutes: '60' })).toEqual({});
  });

  it('auto_close_minutes=1 и =1440 — boundary OK', () => {
    expect(
      validateTiming({ ...baseForm(), auto_close_minutes: '1' }).auto_close_minutes,
    ).toBeUndefined();
    expect(
      validateTiming({ ...baseForm(), auto_close_minutes: '1440' }).auto_close_minutes,
    ).toBeUndefined();
  });
});
