import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import '@/i18n/config';

vi.mock('@/api/addresses', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/addresses')>('@/api/addresses');
  return {
    ...actual,
    createAddress: vi.fn(),
    updateAddress: vi.fn(),
  };
});

vi.mock('@/api/yandex_maps', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/yandex_maps')>(
      '@/api/yandex_maps',
    );
  return {
    ...actual,
    suggest: vi.fn().mockResolvedValue([]),
  };
});

import { createAddress, AddressApiError } from '@/api/addresses';
import { AddressForm } from './AddressForm';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AddressForm submit', () => {
  it('calls createAddress with form data', async () => {
    (createAddress as Mock).mockResolvedValue({
      id: 'a1',
      text: 'Ул. Ленина 1',
      lat: null,
      lon: null,
      label: null,
      apartment: null,
      entrance: null,
      floor: null,
      comment: null,
      is_primary: false,
    });

    const onSaved = vi.fn();
    render(
      <AddressForm onSaved={onSaved} onCancel={() => {}} />,
    );

    // Изменить значение адреса (Autocomplete input — первый text input в форме)
    const inputs = screen.getAllByRole('textbox');
    // [label, address, apartment, entrance, floor, comment]
    fireEvent.change(inputs[1], { target: { value: 'Ул. Ленина 1' } });
    fireEvent.change(inputs[2], { target: { value: '42' } });

    const submit = screen.getByRole('button', {
      name: /сохранить|save/i,
    });
    fireEvent.click(submit);

    await waitFor(() => {
      expect(createAddress).toHaveBeenCalledOnce();
    });

    const payload = (createAddress as Mock).mock.calls[0][0];
    expect(payload.text).toBe('Ул. Ленина 1');
    expect(payload.apartment).toBe('42');

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
  });
});

describe('AddressForm radius error', () => {
  it('shows localized error on 409', async () => {
    (createAddress as Mock).mockRejectedValue(
      new AddressApiError(409, ''),
    );

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[1], { target: { value: 'Далеко' } });

    fireEvent.click(
      screen.getByRole('button', { name: /сохранить|save/i }),
    );

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      // локализованный fallback "Адрес вне зоны доставки"/"outside the delivery zone"
      expect(alert.textContent).toMatch(/вне зоны|outside the delivery zone/i);
    });
  });

  it('preserves server-localized detail on 409', async () => {
    (createAddress as Mock).mockRejectedValue(
      new AddressApiError(409, 'Custom server message'),
    );

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);
    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[1], { target: { value: 'X' } });

    fireEvent.click(
      screen.getByRole('button', { name: /сохранить|save/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain(
        'Custom server message',
      );
    });
  });
});
