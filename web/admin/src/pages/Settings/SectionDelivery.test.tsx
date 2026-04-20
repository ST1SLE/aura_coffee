import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionDelivery } from './SectionDelivery';
import { validateDelivery, type SettingsFormState } from './validation';
import { toKopecks } from '@/api/admin-settings';
import { baseForm } from './testUtils';

describe('SectionDelivery', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('рендерит 4 поля', () => {
    render(
      <SectionDelivery form={baseForm()} onChange={() => {}} errors={{}} />,
    );
    expect(screen.getByLabelText(/Delivery radius/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Min\. delivery order amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Free delivery threshold/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Delivery fee/i)).toBeInTheDocument();
  });

  it('onChange при изменении рублёвого поля эмитит строковое значение', () => {
    const onChange = vi.fn();
    render(<SectionDelivery form={baseForm()} onChange={onChange} errors={{}} />);
    fireEvent.change(screen.getByLabelText(/Delivery fee/i), { target: { value: '200' } });
    expect(onChange).toHaveBeenCalledWith('delivery_fee_rub', '200');
  });

  it('free_delivery_threshold < min_delivery_amount → below_min_delivery', () => {
    const form: SettingsFormState = {
      ...baseForm(),
      min_delivery_amount_rub: '500',
      free_delivery_threshold_rub: '300',
    };
    const errs = validateDelivery(form);
    expect(errs.free_delivery_threshold).toBe('below_min_delivery');
  });

  it('рубли → копейки: 100 ₽ → 10000', () => {
    expect(toKopecks(100)).toBe(10000);
  });

  it('delivery_radius_km=0 → out_of_range', () => {
    const form: SettingsFormState = { ...baseForm(), delivery_radius_km: '0' };
    expect(validateDelivery(form).delivery_radius_km).toBe('out_of_range');
  });

  it('min < free threshold → OK', () => {
    const form: SettingsFormState = {
      ...baseForm(),
      min_delivery_amount_rub: '300',
      free_delivery_threshold_rub: '500',
    };
    expect(validateDelivery(form)).toEqual({});
  });
});
