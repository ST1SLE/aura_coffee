import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { UsersPage } from './UsersPage';
import * as api from '@/api/admin-users';
import type { UserListResponse } from '@/api/admin-users';

function emptyList(): UserListResponse {
  return { items: [], page: 1, per_page: 20, total: 0 };
}

describe('UsersPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.spyOn(api, 'listUsers').mockResolvedValue(emptyList());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  test('default render fires listUsers with no status, page=1', async () => {
    render(<UsersPage />);
    await waitFor(() => {
      expect(api.listUsers).toHaveBeenCalledTimes(1);
    });
    expect(api.listUsers).toHaveBeenLastCalledWith({
      status: 'all',
      search: undefined,
      page: 1,
      perPage: 20,
    });
  });

  test('clicking Active tab refetches with status=active, page=1', async () => {
    render(<UsersPage />);
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId('users-tab-active'));
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(2));
    expect(api.listUsers).toHaveBeenLastCalledWith({
      status: 'active',
      search: undefined,
      page: 1,
      perPage: 20,
    });
  });

  test('typing across 4 keystrokes within 300ms fires ONE debounced refetch', async () => {
    render(<UsersPage />);
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(1));

    const input = screen.getByTestId('users-search');
    fireEvent.change(input, { target: { value: 'i' } });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    fireEvent.change(input, { target: { value: 'iv' } });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    fireEvent.change(input, { target: { value: 'iva' } });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    fireEvent.change(input, { target: { value: 'ivan' } });
    // Still in-debounce — no new call yet
    expect(api.listUsers).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(2));
    expect(api.listUsers).toHaveBeenLastCalledWith({
      status: 'all',
      search: 'ivan',
      page: 1,
      perPage: 20,
    });
  });

  test('clearing search drops search param', async () => {
    render(<UsersPage />);
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(1));
    const input = screen.getByTestId('users-search');

    fireEvent.change(input, { target: { value: 'x' } });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(2));

    fireEvent.change(input, { target: { value: '' } });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(3));
    expect(api.listUsers).toHaveBeenLastCalledWith({
      status: 'all',
      search: undefined,
      page: 1,
      perPage: 20,
    });
  });

  test('clicking pagination next refetches with page=2', async () => {
    vi.mocked(api.listUsers).mockResolvedValue({
      items: [
        {
          id: 'u-1',
          display_name: 'Alice',
          status: 'active',
          loyalty_balance: 0,
          created_at: '2026-04-01T00:00:00Z',
        },
      ],
      page: 1,
      per_page: 20,
      total: 25,
    });
    render(<UsersPage />);
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId('users-next'));
    await waitFor(() => expect(api.listUsers).toHaveBeenCalledTimes(2));
    expect(api.listUsers).toHaveBeenLastCalledWith({
      status: 'all',
      search: undefined,
      page: 2,
      perPage: 20,
    });
  });
});
