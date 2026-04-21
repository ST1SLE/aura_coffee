import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { BlockConfirmDialog } from './BlockConfirmDialog';
import type { UserDetailResponse, BlockUserResponse } from '@/api/admin-users';
import * as api from '@/api/admin-users';

function makeUser(overrides: Partial<UserDetailResponse> = {}): UserDetailResponse {
  return {
    id: overrides.id ?? 'u-1',
    display_name: overrides.display_name ?? 'Иван',
    status: overrides.status ?? 'active',
    language: overrides.language ?? 'ru',
    loyalty_balance: overrides.loyalty_balance ?? 0,
    loyalty_transactions: overrides.loyalty_transactions ?? [],
    active_orders_count: overrides.active_orders_count ?? 0,
    created_at: overrides.created_at ?? '2026-04-01T10:00:00Z',
  };
}

describe('BlockConfirmDialog', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.restoreAllMocks();
  });

  test('confirm button starts disabled; checkbox unchecked', () => {
    render(
      <BlockConfirmDialog
        open
        onClose={vi.fn()}
        user={makeUser({ active_orders_count: 3 })}
        onConfirmed={vi.fn()}
      />,
    );
    const confirmBtn = screen.getByTestId('block-confirm-submit') as HTMLButtonElement;
    expect(confirmBtn).toBeDisabled();
    const checkbox = screen.getByTestId('block-confirm-checkbox') as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
  });

  test('checking the checkbox enables confirm', () => {
    render(
      <BlockConfirmDialog
        open
        onClose={vi.fn()}
        user={makeUser({ active_orders_count: 3 })}
        onConfirmed={vi.fn()}
      />,
    );
    const checkbox = screen.getByTestId('block-confirm-checkbox');
    fireEvent.click(checkbox);
    const confirmBtn = screen.getByTestId('block-confirm-submit') as HTMLButtonElement;
    expect(confirmBtn).not.toBeDisabled();
  });

  test('warning substrings active_orders_count (N=3)', () => {
    render(
      <BlockConfirmDialog
        open
        onClose={vi.fn()}
        user={makeUser({ active_orders_count: 3 })}
        onConfirmed={vi.fn()}
      />,
    );
    const warning = screen.getByTestId('block-confirm-warning');
    expect(warning.textContent).toContain('3');
  });

  test('N=0 still renders dialog and confirm starts disabled', () => {
    render(
      <BlockConfirmDialog
        open
        onClose={vi.fn()}
        user={makeUser({ active_orders_count: 0 })}
        onConfirmed={vi.fn()}
      />,
    );
    expect(screen.getByTestId('block-confirm-warning').textContent).toContain('0');
    const confirmBtn = screen.getByTestId('block-confirm-submit') as HTMLButtonElement;
    expect(confirmBtn).toBeDisabled();
  });

  test('confirm → calls blockUser, fires onConfirmed, shows result line', async () => {
    const response: BlockUserResponse = {
      user_id: 'u-1',
      status: 'blocked',
      cancelled_orders_count: 5,
    };
    const spy = vi.spyOn(api, 'blockUser').mockResolvedValue(response);
    const onConfirmed = vi.fn();
    render(
      <BlockConfirmDialog
        open
        onClose={vi.fn()}
        user={makeUser({ id: 'u-1', active_orders_count: 5 })}
        onConfirmed={onConfirmed}
      />,
    );
    fireEvent.click(screen.getByTestId('block-confirm-checkbox'));
    fireEvent.click(screen.getByTestId('block-confirm-submit'));

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith('u-1');
      expect(onConfirmed).toHaveBeenCalledWith(response);
    });
    const result = await screen.findByTestId('block-confirm-result');
    expect(result.textContent).toContain('5');
  });
});
