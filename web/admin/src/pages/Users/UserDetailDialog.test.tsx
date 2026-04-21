import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { UserDetailDialog } from './UserDetailDialog';
import type {
  UserDetailResponse,
  UserStatus,
  BlockUserResponse,
} from '@/api/admin-users';
import * as api from '@/api/admin-users';

function makeDetail(overrides: Partial<UserDetailResponse> = {}): UserDetailResponse {
  return {
    id: overrides.id ?? 'u-1',
    display_name: overrides.display_name ?? 'Иван',
    status: overrides.status ?? 'active',
    language: overrides.language ?? 'ru',
    loyalty_balance: overrides.loyalty_balance ?? 200,
    loyalty_transactions: overrides.loyalty_transactions ?? [],
    active_orders_count: overrides.active_orders_count ?? 0,
    created_at: overrides.created_at ?? '2026-04-01T10:00:00Z',
  };
}

function renderOpen(
  status: UserStatus,
  opts: {
    onMutated?: () => void;
    detail?: Partial<UserDetailResponse>;
  } = {},
) {
  const onMutated = opts.onMutated ?? vi.fn();
  const detail = makeDetail({ status, ...opts.detail });
  const spy = vi.spyOn(api, 'getUser').mockResolvedValue(detail);
  const utils = render(
    <UserDetailDialog
      userId="u-1"
      open
      onClose={vi.fn()}
      onMutated={onMutated}
    />,
  );
  return { ...utils, onMutated, detail, getUserSpy: spy };
}

describe('UserDetailDialog', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.restoreAllMocks();
  });

  test('renders transactions in server-provided order', async () => {
    renderOpen('active', {
      detail: {
        loyalty_transactions: [
          {
            id: 't-1',
            type: 'accrual',
            amount: 100,
            balance_after: 300,
            description: 'a',
            created_at: '2026-04-03T10:00:00Z',
          },
          {
            id: 't-2',
            type: 'redemption',
            amount: -50,
            balance_after: 200,
            description: 'b',
            created_at: '2026-04-02T10:00:00Z',
          },
          {
            id: 't-3',
            type: 'admin_adjustment',
            amount: 25,
            balance_after: 175,
            description: 'c',
            created_at: '2026-04-01T10:00:00Z',
          },
        ],
      },
    });
    const rows = await screen.findAllByTestId(/^tx-row-/);
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual([
      'tx-row-t-1',
      'tx-row-t-2',
      'tx-row-t-3',
    ]);
  });

  test('status=active shows Block+Adjust, hides Unblock', async () => {
    renderOpen('active');
    await screen.findByTestId('user-detail-block');
    expect(screen.getByTestId('user-detail-adjust')).toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-unblock')).not.toBeInTheDocument();
  });

  test('status=blocked shows Unblock+Adjust, hides Block', async () => {
    renderOpen('blocked');
    await screen.findByTestId('user-detail-unblock');
    expect(screen.getByTestId('user-detail-adjust')).toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-block')).not.toBeInTheDocument();
  });

  test('status=pending_verification shows no action buttons', async () => {
    renderOpen('pending_verification');
    await screen.findByTestId('user-detail-header');
    expect(screen.queryByTestId('user-detail-block')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-unblock')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-adjust')).not.toBeInTheDocument();
  });

  test('status=deleted shows no action buttons', async () => {
    renderOpen('deleted');
    await screen.findByTestId('user-detail-header');
    expect(screen.queryByTestId('user-detail-block')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-unblock')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-detail-adjust')).not.toBeInTheDocument();
  });

  test('signed-amount formatting: -50 renders "-50", +100 renders "+100"', async () => {
    renderOpen('active', {
      detail: {
        loyalty_transactions: [
          {
            id: 'p',
            type: 'accrual',
            amount: 100,
            balance_after: 300,
            description: null,
            created_at: '2026-04-01T10:00:00Z',
          },
          {
            id: 'n',
            type: 'redemption',
            amount: -50,
            balance_after: 200,
            description: null,
            created_at: '2026-04-01T10:00:00Z',
          },
        ],
      },
    });
    await screen.findByTestId('tx-row-p');
    expect(screen.getByTestId('tx-amount-p').textContent).toBe('+100');
    expect(screen.getByTestId('tx-amount-n').textContent).toBe('-50');
  });

  test('DOM contains no phone/phone_hash', async () => {
    const { container } = renderOpen('active');
    await screen.findByTestId('user-detail-header');
    const html = container.innerHTML.toLowerCase();
    expect(html).not.toContain('phone');
  });

  test('Block → opens BlockConfirmDialog → onConfirmed triggers onMutated + refetch', async () => {
    const blockResp: BlockUserResponse = {
      user_id: 'u-1',
      status: 'blocked',
      cancelled_orders_count: 2,
    };
    const blockSpy = vi.spyOn(api, 'blockUser').mockResolvedValue(blockResp);
    const { onMutated, getUserSpy } = renderOpen('active', {
      detail: { active_orders_count: 2 },
    });
    await screen.findByTestId('user-detail-block');
    // Before clicking Block: getUser called once (initial load)
    expect(getUserSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('user-detail-block'));
    // Block confirm dialog visible
    const checkbox = await screen.findByTestId('block-confirm-checkbox');
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByTestId('block-confirm-submit'));

    await waitFor(() => {
      expect(blockSpy).toHaveBeenCalledWith('u-1');
      expect(onMutated).toHaveBeenCalled();
      // refetch of detail after mutation
      expect(getUserSpy).toHaveBeenCalledTimes(2);
    });
  });

  test('Unblock → fires unblockUser → onMutated + refetch', async () => {
    const unblockSpy = vi.spyOn(api, 'unblockUser').mockResolvedValue({
      user_id: 'u-1',
      status: 'active',
    });
    const { onMutated, getUserSpy } = renderOpen('blocked');
    await screen.findByTestId('user-detail-unblock');
    expect(getUserSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('user-detail-unblock'));
    await waitFor(() => {
      expect(unblockSpy).toHaveBeenCalledWith('u-1');
      expect(onMutated).toHaveBeenCalled();
      expect(getUserSpy).toHaveBeenCalledTimes(2);
    });
  });

  test('Adjust → open form → submit → onMutated + refetch', async () => {
    vi.spyOn(api, 'adjustLoyalty').mockResolvedValue({
      transaction_id: 'tx-new',
      new_balance: 250,
      delta: 50,
    });
    const { onMutated, getUserSpy } = renderOpen('active');
    await screen.findByTestId('user-detail-adjust');
    expect(getUserSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('user-detail-adjust'));
    fireEvent.change(await screen.findByTestId('adjust-delta'), {
      target: { value: '50' },
    });
    fireEvent.change(screen.getByTestId('adjust-reason'), {
      target: { value: 'bonus' },
    });
    fireEvent.click(screen.getByTestId('adjust-submit'));

    await waitFor(() => {
      expect(onMutated).toHaveBeenCalled();
      expect(getUserSpy).toHaveBeenCalledTimes(2);
    });
  });
});
