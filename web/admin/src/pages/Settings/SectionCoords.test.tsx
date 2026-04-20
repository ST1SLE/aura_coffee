import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionCoords } from './SectionCoords';
import { validateCoords, type SettingsFormState } from './validation';
import { baseForm } from './testUtils';

describe('SectionCoords', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('рендерит shop_lat и shop_lon', () => {
    render(
      <SectionCoords form={baseForm()} onChange={() => {}} errors={{}} />,
    );
    expect(screen.getByLabelText(/Latitude/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Longitude/i)).toBeInTheDocument();
  });

  it('onChange вызывается при редактировании', () => {
    const onChange = vi.fn();
    render(<SectionCoords form={baseForm()} onChange={onChange} errors={{}} />);
    fireEvent.change(screen.getByLabelText(/Latitude/i), { target: { value: '60' } });
    expect(onChange).toHaveBeenCalledWith('shop_lat', '60');
  });

  it('inline error при errors.shop_lat', () => {
    render(
      <SectionCoords
        form={baseForm()}
        onChange={() => {}}
        errors={{ shop_lat: 'out_of_range' }}
      />,
    );
    expect(screen.getByTestId('err-shop_lat')).toBeInTheDocument();
  });

  it('validateCoords: lat=91 → out_of_range', () => {
    const form: SettingsFormState = { ...baseForm(), shop_lat: '91' };
    expect(validateCoords(form).shop_lat).toBe('out_of_range');
  });

  it('validateCoords: lat=55.75 lon=37.62 → OK', () => {
    expect(validateCoords(baseForm())).toEqual({});
  });
});
