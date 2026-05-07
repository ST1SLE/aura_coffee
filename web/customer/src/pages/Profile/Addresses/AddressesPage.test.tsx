import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  type Mock,
} from 'vitest';
import { render, fireEvent, waitFor, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import '@/i18n/config';

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

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal(
    'confirm',
    vi.fn(() => true),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('AddressesPage delete', () => {
  it('confirms, calls DELETE, and refreshes the list', async () => {
    (listAddresses as Mock)
      .mockResolvedValueOnce([address()])
      .mockResolvedValueOnce([]);
    (deleteAddress as Mock).mockResolvedValue(undefined);

    render(<AddressesPage />);

    expect(await screen.findByText('Работа')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /удалить|delete/i }));

    await waitFor(() => {
      expect(deleteAddress).toHaveBeenCalledWith('a2');
    });
    await waitFor(() => {
      expect(listAddresses).toHaveBeenCalledTimes(2);
    });
    expect(globalThis.confirm).toHaveBeenCalled();
    expect(screen.queryByText('Работа')).not.toBeInTheDocument();
    expect(
      screen.getByText(/сохраните адрес|save an address/i),
    ).toBeInTheDocument();
  });
});
