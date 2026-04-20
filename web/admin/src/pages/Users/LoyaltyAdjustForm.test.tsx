import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { LoyaltyAdjustForm } from './LoyaltyAdjustForm';
import * as api from '@/api/admin-users';
import { ApiError } from '@/api/admin-users';

function setup(
  overrides: {
    onSuccess?: () => void;
    onNotify?: (msg: string, variant: 'success' | 'error') => void;
  } = {},
) {
  const onSuccess = overrides.onSuccess ?? vi.fn();
  const onNotify = overrides.onNotify ?? vi.fn();
  const utils = render(
    <LoyaltyAdjustForm
      userId="u-1"
      onSuccess={onSuccess}
      onNotify={onNotify}
    />,
  );
  return { ...utils, onSuccess, onNotify };
}

function submit() {
  fireEvent.click(screen.getByTestId('adjust-submit'));
}

describe('LoyaltyAdjustForm', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.restoreAllMocks();
  });

  test('delta=0 with reason shows inline delta error, no HTTP', async () => {
    const spy = vi.spyOn(api, 'adjustLoyalty');
    setup();
    fireEvent.change(screen.getByTestId('adjust-delta'), { target: { value: '0' } });
    fireEvent.change(screen.getByTestId('adjust-reason'), { target: { value: 'test' } });
    submit();
    await waitFor(() => {
      expect(screen.getByTestId('adjust-error-delta')).toBeInTheDocument();
    });
    expect(spy).not.toHaveBeenCalled();
  });

  test('empty reason shows inline reason error, no HTTP', async () => {
    const spy = vi.spyOn(api, 'adjustLoyalty');
    setup();
    fireEvent.change(screen.getByTestId('adjust-delta'), { target: { value: '100' } });
    fireEvent.change(screen.getByTestId('adjust-reason'), { target: { value: '' } });
    submit();
    await waitFor(() => {
      expect(screen.getByTestId('adjust-error-reason')).toBeInTheDocument();
    });
    expect(spy).not.toHaveBeenCalled();
  });

  test('reason length 501 shows inline reason error, no HTTP', async () => {
    const spy = vi.spyOn(api, 'adjustLoyalty');
    setup();
    fireEvent.change(screen.getByTestId('adjust-delta'), { target: { value: '100' } });
    fireEvent.change(screen.getByTestId('adjust-reason'), {
      target: { value: 'x'.repeat(501) },
    });
    submit();
    await waitFor(() => {
      expect(screen.getByTestId('adjust-error-reason')).toBeInTheDocument();
    });
    expect(spy).not.toHaveBeenCalled();
  });

  test('happy path: onSuccess + form cleared + notifier success', async () => {
    const spy = vi.spyOn(api, 'adjustLoyalty').mockResolvedValue({
      transaction_id: 'tx-1',
      new_balance: 150,
      delta: 50,
    });
    const { onSuccess, onNotify } = setup();
    const delta = screen.getByTestId('adjust-delta') as HTMLInputElement;
    const reason = screen.getByTestId('adjust-reason') as HTMLTextAreaElement;
    fireEvent.change(delta, { target: { value: '50' } });
    fireEvent.change(reason, { target: { value: 'manual bonus' } });
    submit();
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith('u-1', { delta: 50, reason: 'manual bonus' });
      expect(onSuccess).toHaveBeenCalled();
    });
    expect(delta.value).toBe('');
    expect(reason.value).toBe('');
    expect(onNotify).toHaveBeenCalledWith(expect.any(String), 'success');
  });

  test('422 insufficient_balance → delta inline error; form not cleared; no onSuccess', async () => {
    vi.spyOn(api, 'adjustLoyalty').mockRejectedValue(
      new ApiError(422, { detail: 'insufficient_balance' }, 'api error'),
    );
    const { onSuccess } = setup();
    const delta = screen.getByTestId('adjust-delta') as HTMLInputElement;
    const reason = screen.getByTestId('adjust-reason') as HTMLTextAreaElement;
    fireEvent.change(delta, { target: { value: '-1000' } });
    fireEvent.change(reason, { target: { value: 'oops' } });
    submit();
    await waitFor(() => {
      expect(screen.getByTestId('adjust-error-delta')).toBeInTheDocument();
    });
    expect(delta.value).toBe('-1000');
    expect(reason.value).toBe('oops');
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
