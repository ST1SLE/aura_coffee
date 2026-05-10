import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  type Mock,
} from 'vitest';
import {
  render,
  fireEvent,
  waitFor,
  screen,
  within,
} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import i18n from '@/i18n/config';

vi.mock('@/api/addresses', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/addresses')>('@/api/addresses');
  return {
    ...actual,
    listAddresses: vi.fn(),
    deleteAddress: vi.fn(),
    setDefaultAddress: vi.fn(),
  };
});

import {
  listAddresses,
  deleteAddress,
  type AddressResponse,
} from '@/api/addresses';
import { AddressesPage } from './AddressesPage';

const address = (over: Partial<AddressResponse> = {}): AddressResponse => ({
  id: 'a2',
  address_text: 'Москва, ул. Льва Толстого, 16',
  lat: 55.733,
  lon: 37.588,
  label: 'Работа',
  apartment: '12',
  entrance: '3',
  floor: null,
  comment: null,
  is_default: false,
  ...over,
});

beforeEach(async () => {
  vi.clearAllMocks();
  localStorage.clear();
  await i18n.changeLanguage('ru');
});

describe('AddressesPage delete', () => {
  it('opens an in-app confirmation dialog before DELETE and refreshes the list', async () => {
    (listAddresses as Mock)
      .mockResolvedValueOnce([address()])
      .mockResolvedValueOnce([]);
    (deleteAddress as Mock).mockResolvedValue(undefined);

    render(<AddressesPage />);

    expect(await screen.findByText('Работа')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /удалить|delete/i }));
    expect(deleteAddress).not.toHaveBeenCalled();

    const dialog = await screen.findByRole('dialog', {
      name: /удалить этот адрес|delete this address/i,
    });
    expect(dialog).toHaveTextContent('Работа');
    expect(dialog).toHaveTextContent('Москва, ул. Льва Толстого, 16');

    fireEvent.click(
      within(dialog).getByRole('button', { name: /удалить|delete/i }),
    );

    await waitFor(() => expect(deleteAddress).toHaveBeenCalledWith('a2'));
    await waitFor(() => {
      expect(listAddresses).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText('Работа')).not.toBeInTheDocument();
    expect(
      screen.getByText(/сохраните адрес|save an address/i),
    ).toBeInTheDocument();
  });

  it('cancels address deletion without calling DELETE', async () => {
    (listAddresses as Mock).mockResolvedValue([address()]);

    render(<AddressesPage />);

    expect(await screen.findByText('Работа')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /удалить|delete/i }));

    const dialog = await screen.findByRole('dialog', {
      name: /удалить этот адрес|delete this address/i,
    });
    fireEvent.click(
      within(dialog).getByRole('button', { name: /отменить|cancel/i }),
    );

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(deleteAddress).not.toHaveBeenCalled();
    expect(screen.getByText('Работа')).toBeInTheDocument();
  });

  it('localizes apartment, entrance, and floor labels', async () => {
    await i18n.changeLanguage('en');
    (listAddresses as Mock).mockResolvedValue([
      address({
        label: 'Work',
        apartment: '12',
        entrance: '3',
        floor: '7',
      }),
    ]);

    render(<AddressesPage />);

    expect(await screen.findByText('Work')).toBeInTheDocument();
    expect(screen.getByText(/Apartment: 12/i)).toBeInTheDocument();
    expect(screen.getByText(/Entrance: 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Floor: 7/i)).toBeInTheDocument();
  });
});
