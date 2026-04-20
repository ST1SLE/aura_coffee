import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { PromoFormDialog } from './PromoFormDialog';
import type { PromocodeResponse } from '@/api/promocodes';
import * as promoApi from '@/api/promocodes';

vi.mock('@/api/promocodes', async () => {
  const actual = await vi.importActual<typeof import('@/api/promocodes')>('@/api/promocodes');
  return {
    ...actual,
    createPromocode: vi.fn(),
    updatePromocode: vi.fn(),
    activatePromocode: vi.fn(),
    deactivatePromocode: vi.fn(),
  };
});

function makePromo(overrides: Partial<PromocodeResponse> = {}): PromocodeResponse {
  return {
    id: 'id-1',
    code: 'WEEK',
    discount_type: 'fixed_amount',
    discount_value: 50000,
    min_order_amount: 100000,
    valid_from: null,
    valid_until: null,
    max_uses: null,
    max_uses_per_user: null,
    current_uses: 0,
    is_active: false,
    state: 'inactive',
    created_at: '2026-04-20T10:00:00Z',
    ...overrides,
  };
}

describe('PromoFormDialog', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await i18n.changeLanguage('en');
  });

  test('edit-mode current_uses=0 — all lockable fields editable', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ current_uses: 0 })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Code')).not.toBeDisabled();
    expect(screen.getByDisplayValue('fixed_amount')).not.toBeDisabled();
    // discount_value input: find by display value 500 (50000 kop / 100)
    const valueInput = screen.getByDisplayValue('500');
    expect(valueInput).not.toBeDisabled();
  });

  test('edit-mode current_uses>0 — code, discount_type, discount_value disabled', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ current_uses: 3 })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Code')).toBeDisabled();
    // radio inputs for discount_type
    expect(screen.getByDisplayValue('percent')).toBeDisabled();
    expect(screen.getByDisplayValue('fixed_amount')).toBeDisabled();
    expect(screen.getByDisplayValue('500')).toBeDisabled();
  });

  test('kopecks → rubles on load for fixed_amount', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({
          discount_type: 'fixed_amount',
          discount_value: 50000,
          min_order_amount: 100000,
        })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    // rubles display: 500 and 1000
    expect(screen.getByDisplayValue('500')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1000')).toBeInTheDocument();
  });

  test('percent stays integer on load', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({
          discount_type: 'percent',
          discount_value: 10,
          min_order_amount: 0,
        })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue('10')).toBeInTheDocument();
  });

  test('rubles → kopecks on save (create) — fixed_amount', async () => {
    vi.mocked(promoApi.createPromocode).mockResolvedValue(makePromo());
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={null}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: 'X' } });
    fireEvent.click(screen.getByDisplayValue('fixed_amount'));
    const valueInput = screen.getByLabelText(/Discount Value/);
    fireEvent.change(valueInput, { target: { value: '500' } });
    const minInput = screen.getByLabelText(/Min Order Amount/);
    fireEvent.change(minInput, { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(promoApi.createPromocode).toHaveBeenCalled());
    const arg = vi.mocked(promoApi.createPromocode).mock.calls[0][0];
    expect(arg.discount_value_rubles).toBe(500);
    expect(arg.min_order_rubles).toBe(1000);
    expect(arg.discount_type).toBe('fixed_amount');
  });

  test('footer: inactive+eligible renders Activate, no Deactivate', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ is_active: false, state: 'inactive' })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'Activate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  test('footer: active renders Deactivate, no Activate', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ is_active: true, state: 'active' })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
  });

  test('footer: expired inactive renders neither Activate nor Deactivate', () => {
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ is_active: false, state: 'expired' })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  test('Activate button dispatches activatePromocode, not updatePromocode', async () => {
    vi.mocked(promoApi.activatePromocode).mockResolvedValue(
      makePromo({ is_active: true, state: 'active' }),
    );
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ is_active: false, state: 'inactive' })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Activate' }));
    await waitFor(() => expect(promoApi.activatePromocode).toHaveBeenCalledWith('id-1'));
    expect(promoApi.updatePromocode).not.toHaveBeenCalled();
  });

  test('server 422 field_locked_after_use surfaces localized inline error on code', async () => {
    const apiErr = new promoApi.ApiError(
      422,
      {
        detail: [{ loc: ['body', 'code'], msg: 'field_locked_after_use', type: 'value_error' }],
      },
      'HTTP 422',
    );
    vi.mocked(promoApi.updatePromocode).mockRejectedValue(apiErr);
    render(
      <PromoFormDialog
        open
        onClose={vi.fn()}
        promo={makePromo({ current_uses: 0 })}
        onSaved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(screen.getByText('Field cannot be changed after first use')).toBeInTheDocument(),
    );
  });
});
