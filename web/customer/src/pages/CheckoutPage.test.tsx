import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@/i18n/config';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('@/api/orders', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/orders')>('@/api/orders');
  return {
    ...actual,
    createOrder: vi.fn(),
  };
});

vi.mock('@/api/addresses', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/addresses')>('@/api/addresses');
  return {
    ...actual,
    listAddresses: vi.fn(),
    createAddress: vi.fn(),
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

import { createOrder, OrderApiError } from '@/api/orders';
import {
  listAddresses,
  createAddress,
  type AddressResponse,
} from '@/api/addresses';
import { geocode, MapsUnavailableError } from '@/api/yandex_maps';
import { CheckoutPage } from './CheckoutPage';

const order = {
  id: 'o1',
  status: 'created',
  type: 'pickup' as const,
  items: [],
  subtotal: 0,
  discount_amount: 0,
  points_used: 0,
  delivery_fee: 0,
  total: 0,
  estimated_accrual: 0,
  created_at: 'now',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <CheckoutPage />
    </MemoryRouter>,
  );
}

const savedA: AddressResponse = {
  id: 'saved-1',
  address_text: 'Невский 1',
  lat: 1,
  lon: 2,
  label: 'Дом',
  apartment: '10',
  entrance: null,
  floor: null,
  comment: null,
  is_default: true,
};
const savedB: AddressResponse = {
  id: 'saved-2',
  address_text: 'Невский 2',
  lat: 1,
  lon: 2,
  label: null,
  apartment: null,
  entrance: null,
  floor: null,
  comment: null,
  is_default: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  (geocode as Mock).mockImplementation((text: string) =>
    Promise.resolve({
      canonical_text: text,
      lat: 55.75,
      lon: 37.61,
      precision: 'exact',
    }),
  );
});

describe('CheckoutPage default pickup', () => {
  it('submits pickup payload by default', async () => {
    (createOrder as Mock).mockResolvedValue(order);
    (listAddresses as Mock).mockResolvedValue([]);
    renderPage();

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(createOrder).toHaveBeenCalledOnce();
    });
    expect(createOrder).toHaveBeenCalledWith({ type: 'pickup' });
    expect(mockNavigate).toHaveBeenCalledWith('/orders/o1');
  });
});

describe('CheckoutPage delivery with saved', () => {
  it('shows saved/new radio and preselects primary', async () => {
    (listAddresses as Mock).mockResolvedValue([savedA, savedB]);
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));

    await waitFor(() => {
      expect(listAddresses).toHaveBeenCalled();
    });

    // radio "Сохранённый адрес" есть и выбран
    const savedRadio = screen.getByLabelText(
      /сохранённый адрес|saved address/i,
    ) as HTMLInputElement;
    expect(savedRadio.checked).toBe(true);

    // primary (savedA) предвыбран
    await waitFor(() => {
      const primaryRadio = screen.getByDisplayValue(
        'saved-1',
      ) as HTMLInputElement;
      expect(primaryRadio.checked).toBe(true);
    });
  });

  it('submits with delivery_address_id only', async () => {
    (listAddresses as Mock).mockResolvedValue([savedA, savedB]);
    (createOrder as Mock).mockResolvedValue(order);
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => expect(createOrder).toHaveBeenCalled());
    const payload = (createOrder as Mock).mock.calls[0][0];
    expect(payload).toEqual({
      type: 'delivery',
      delivery_address_id: 'saved-1',
    });
    expect(payload.delivery_address).toBeUndefined();
  });
});

describe('CheckoutPage delivery with new address', () => {
  it('geocodes typed address before createOrder and submits numbers', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (geocode as Mock).mockResolvedValue({
      canonical_text: 'Россия, Санкт-Петербург, Новый адрес 5',
      lat: 59.93,
      lon: 30.36,
      precision: 'exact',
    });
    (createOrder as Mock).mockResolvedValue(order);
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    // no saved → new form is active. The address autocomplete input is the
    // first textbox inside the delivery block.
    const textboxes = screen.getAllByRole('textbox');
    // [autocomplete, apartment, entrance, floor, comment]
    fireEvent.change(textboxes[0], { target: { value: 'Новый адрес 5' } });
    fireEvent.change(textboxes[1], { target: { value: '10' } });

    fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

    await waitFor(() => expect(createOrder).toHaveBeenCalled());
    expect(geocode).toHaveBeenCalledWith('Новый адрес 5', expect.any(String));
    expect((geocode as Mock).mock.invocationCallOrder[0]).toBeLessThan(
      (createOrder as Mock).mock.invocationCallOrder[0],
    );
    const payload = (createOrder as Mock).mock.calls[0][0];
    expect(payload.type).toBe('delivery');
    expect(payload.delivery_address).toEqual({
      text: 'Россия, Санкт-Петербург, Новый адрес 5',
      lat: 59.93,
      lon: 30.36,
      apartment: '10',
      entrance: null,
      floor: null,
      comment: null,
    });
    expect(payload.delivery_address_id).toBeUndefined();
  });

  it('saveForFuture=true calls createAddress after createOrder', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (createOrder as Mock).mockResolvedValue(order);
    (createAddress as Mock).mockResolvedValue({ ...savedA });
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    const textboxes = screen.getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'Адрес' } });
    fireEvent.click(
      screen.getByLabelText(/сохранить для следующего|save for next/i),
    );

    fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

    await waitFor(() => expect(createAddress).toHaveBeenCalled());
    // Порядок: сначала order, потом save
    const createOrderOrder = (createOrder as Mock).mock.invocationCallOrder[0];
    const createAddrOrder = (createAddress as Mock).mock.invocationCallOrder[0];
    expect(createAddrOrder).toBeGreaterThan(createOrderOrder);
  });

  it('saveForFuture address-save failure does not log raw address text', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (createOrder as Mock).mockResolvedValue(order);
    (createAddress as Mock).mockRejectedValue(new Error('Адрес'));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    try {
      renderPage();

      fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
      await waitFor(() => expect(listAddresses).toHaveBeenCalled());

      const textboxes = screen.getAllByRole('textbox');
      fireEvent.change(textboxes[0], { target: { value: 'Адрес' } });
      fireEvent.click(
        screen.getByLabelText(/сохранить для следующего|save for next/i),
      );

      fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

      await waitFor(() =>
        expect(mockNavigate).toHaveBeenCalledWith('/orders/o1'),
      );
      expect(warn).toHaveBeenCalledWith('Failed to save address for future');
      expect(warn.mock.calls.flat().join(' ')).not.toContain('Адрес');
    } finally {
      warn.mockRestore();
    }
  });

  it('saveForFuture=false does NOT call createAddress', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (createOrder as Mock).mockResolvedValue(order);
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    const textboxes = screen.getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'Адрес' } });

    fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

    await waitFor(() => expect(createOrder).toHaveBeenCalled());
    expect(createAddress).not.toHaveBeenCalled();
  });

  it('shows localized maps-unavailable error when typed address cannot geocode', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (geocode as Mock).mockRejectedValue(new MapsUnavailableError());
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    const textboxes = screen.getAllByRole('textbox');
    fireEvent.change(textboxes[0], {
      target: { value: 'Адрес без координат' },
    });

    fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(
        /сервис проверки адреса|address validation service/i,
      );
    });
    expect(createOrder).not.toHaveBeenCalled();
  });
});

describe('CheckoutPage 409 rendering', () => {
  it('renders detail and keeps form open', async () => {
    (listAddresses as Mock).mockResolvedValue([]);
    (createOrder as Mock).mockRejectedValue(
      new OrderApiError(409, 'Адрес вне зоны доставки (максимум 10 км).'),
    );
    renderPage();

    fireEvent.click(screen.getByLabelText(/доставка|delivery/i));
    await waitFor(() => expect(listAddresses).toHaveBeenCalled());

    const textboxes = screen.getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'Далеко' } });

    fireEvent.click(screen.getByRole('button', { name: /оформить|place/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('вне зоны');
    });
    expect(mockNavigate).not.toHaveBeenCalled();
    // форма всё ещё видна
    expect(
      screen.getByRole('button', { name: /оформить|place/i }),
    ).not.toBeNull();
  });
});
