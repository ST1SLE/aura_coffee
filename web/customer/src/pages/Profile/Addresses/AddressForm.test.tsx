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
    geocode: vi.fn(),
  };
});

import { createAddress, updateAddress, AddressApiError } from '@/api/addresses';
import { geocode, MapsUnavailableError, suggest } from '@/api/yandex_maps';
import { AddressForm } from './AddressForm';

async function selectSuggestedAddress(
  input: HTMLElement,
  text: string,
  lat = 55.7558,
  lon = 37.6173,
) {
  (suggest as Mock).mockResolvedValueOnce([{ text, lat, lon }]);
  fireEvent.change(input, { target: { value: text } });
  await waitFor(() => {
    expect(suggest).toHaveBeenCalledWith(text, expect.any(String));
  });
  await waitFor(() => screen.getByText(text));
  fireEvent.mouseDown(screen.getByText(text));
}

function getAddressFormFields() {
  const textboxes = screen.getAllByRole('textbox');
  return {
    labelInput: textboxes[0],
    addressInput: screen.getByRole('combobox'),
    apartmentInput: textboxes[1],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  (suggest as Mock).mockResolvedValue([]);
  (geocode as Mock).mockResolvedValue(null);
});

describe('AddressForm submit', () => {
  it('calls createAddress with address_text and label', async () => {
    (createAddress as Mock).mockResolvedValue({
      id: 'a1',
      address_text: 'Ул. Ленина 1',
      lat: null,
      lon: null,
      label: 'Дом',
      apartment: null,
      entrance: null,
      floor: null,
      comment: null,
      is_default: false,
    });

    const onSaved = vi.fn();
    render(<AddressForm onSaved={onSaved} onCancel={() => {}} />);

    const { labelInput, addressInput, apartmentInput } = getAddressFormFields();
    fireEvent.change(labelInput, { target: { value: 'Дом' } });
    await selectSuggestedAddress(addressInput, 'Ул. Ленина 1');
    fireEvent.change(apartmentInput, { target: { value: '42' } });

    const submit = screen.getByRole('button', {
      name: /сохранить|save/i,
    });
    fireEvent.click(submit);

    await waitFor(() => {
      expect(createAddress).toHaveBeenCalledOnce();
    });

    const payload = (createAddress as Mock).mock.calls[0][0];
    expect(payload.address_text).toBe('Ул. Ленина 1');
    expect(payload.label).toBe('Дом');
    expect(payload.apartment).toBe('42');
    expect(payload).not.toHaveProperty('text');

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it('disables Save button when label is empty', () => {
    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'Ул. Ленина 1' },
    });

    const submit = screen.getByRole('button', {
      name: /сохранить|save/i,
    }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
  });

  it('geocodes typed address before creating when no suggestion was selected', async () => {
    (geocode as Mock).mockResolvedValue({
      canonical_text: 'Россия, Москва, ул. Ленина, 1',
      lat: 55.7558,
      lon: 37.6173,
      precision: 'exact',
    });
    (createAddress as Mock).mockResolvedValue({
      id: 'a1',
      address_text: 'Россия, Москва, ул. Ленина, 1',
      lat: 55.7558,
      lon: 37.6173,
      label: 'Дом',
      apartment: null,
      entrance: null,
      floor: null,
      comment: null,
      is_default: false,
    });

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);

    const { labelInput, addressInput } = getAddressFormFields();
    fireEvent.change(labelInput, { target: { value: 'Дом' } });
    fireEvent.change(addressInput, { target: { value: 'Ул. Ленина 1' } });

    fireEvent.click(screen.getByRole('button', { name: /сохранить|save/i }));

    await waitFor(() => {
      expect(geocode).toHaveBeenCalledWith('Ул. Ленина 1', expect.any(String));
      expect(createAddress).toHaveBeenCalledOnce();
    });
    const payload = (createAddress as Mock).mock.calls[0][0];
    expect(payload.address_text).toBe('Россия, Москва, ул. Ленина, 1');
    expect(payload.lat).toBe(55.7558);
    expect(payload.lon).toBe(37.6173);
  });

  it('shows maps-unavailable when typed address cannot be geocoded', async () => {
    (geocode as Mock).mockRejectedValue(new MapsUnavailableError());

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);

    const { labelInput, addressInput } = getAddressFormFields();
    fireEvent.change(labelInput, { target: { value: 'Дом' } });
    fireEvent.change(addressInput, { target: { value: 'Ул. Ленина 1' } });

    fireEvent.click(screen.getByRole('button', { name: /сохранить|save/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(
        /сервис проверки адреса|address validation service/i,
      );
    });
    expect(createAddress).not.toHaveBeenCalled();
  });

  it('PATCHes existing address fields without forbidden lat/lon', async () => {
    const initial = {
      id: 'a1',
      address_text: 'Москва, Красная площадь, 1',
      lat: 55.7558,
      lon: 37.6173,
      label: 'Дом',
      apartment: '12',
      entrance: '2',
      floor: '3',
      comment: null,
      is_default: true,
    };
    (updateAddress as Mock).mockResolvedValue({
      ...initial,
      apartment: '42',
    });

    render(
      <AddressForm initial={initial} onSaved={vi.fn()} onCancel={() => {}} />,
    );

    const { apartmentInput } = getAddressFormFields();
    fireEvent.change(apartmentInput, { target: { value: '42' } });

    fireEvent.click(screen.getByRole('button', { name: /сохранить|save/i }));

    await waitFor(() => {
      expect(updateAddress).toHaveBeenCalledOnce();
    });
    const [, payload] = (updateAddress as Mock).mock.calls[0];
    expect(payload).not.toHaveProperty('lat');
    expect(payload).not.toHaveProperty('lon');
    expect(payload.apartment).toBe('42');
  });
});

describe('AddressForm radius error', () => {
  it('shows localized error on 409', async () => {
    (createAddress as Mock).mockRejectedValue(new AddressApiError(409, ''));

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);

    const { labelInput, addressInput } = getAddressFormFields();
    fireEvent.change(labelInput, { target: { value: 'Дом' } });
    await selectSuggestedAddress(addressInput, 'Далеко', 0, 0);

    fireEvent.click(screen.getByRole('button', { name: /сохранить|save/i }));

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert.textContent).toMatch(/вне зоны|outside the delivery zone/i);
    });
  });

  it('preserves server-localized detail on 409', async () => {
    (createAddress as Mock).mockRejectedValue(
      new AddressApiError(409, 'Custom server message'),
    );

    render(<AddressForm onSaved={vi.fn()} onCancel={() => {}} />);
    const { labelInput, addressInput } = getAddressFormFields();
    fireEvent.change(labelInput, { target: { value: 'Дом' } });
    await selectSuggestedAddress(addressInput, 'Адрес X', 0, 0);

    fireEvent.click(screen.getByRole('button', { name: /сохранить|save/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain(
        'Custom server message',
      );
    });
  });
});
