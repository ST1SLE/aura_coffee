import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { PromosTable } from './PromosTable';
import type { PromocodeResponse } from '@/api/promocodes';

function makePromo(overrides: Partial<PromocodeResponse> = {}): PromocodeResponse {
  return {
    id: overrides.id ?? 'id-1',
    code: overrides.code ?? 'WEEK',
    discount_type: 'percent',
    discount_value: 10,
    min_order_amount: 0,
    valid_from: null,
    valid_until: null,
    max_uses: null,
    max_uses_per_user: null,
    current_uses: 0,
    is_active: true,
    state: 'active',
    created_at: '2026-04-20T10:00:00Z',
    ...overrides,
  };
}

describe('PromosTable', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  test('renders state chip for each of the four states', () => {
    const items = [
      makePromo({ id: '1', code: 'A', state: 'active' }),
      makePromo({ id: '2', code: 'B', state: 'inactive' }),
      makePromo({ id: '3', code: 'C', state: 'expired' }),
      makePromo({ id: '4', code: 'D', state: 'exhausted' }),
    ];
    render(
      <PromosTable
        items={items}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByText('Expired')).toBeInTheDocument();
    expect(screen.getByText('Exhausted')).toBeInTheDocument();
  });

  test('active row shows Deactivate and no Activate', () => {
    render(
      <PromosTable
        items={[makePromo({ state: 'active' })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
  });

  test('inactive row shows Activate and no Deactivate', () => {
    render(
      <PromosTable
        items={[makePromo({ state: 'inactive', is_active: false })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByRole('button', { name: 'Activate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  test('expired row shows no Activate and no Deactivate (only Edit)', () => {
    render(
      <PromosTable
        items={[makePromo({ state: 'expired', is_active: false })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });

  test('exhausted row shows no Activate', () => {
    render(
      <PromosTable
        items={[makePromo({ state: 'exhausted', is_active: true })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
  });

  test('uses column renders "3 / ∞" for unbounded quota', () => {
    render(
      <PromosTable
        items={[makePromo({ current_uses: 3, max_uses: null })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByText('3 / ∞')).toBeInTheDocument();
  });

  test('expired row dims valid_until cell', () => {
    render(
      <PromosTable
        items={[makePromo({ code: 'EXP', state: 'expired', valid_until: '2020-01-01T00:00:00Z' })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    const cell = screen.getByTestId('valid-until-EXP');
    expect(cell.className).toContain('text-muted-foreground');
  });

  test('in-flight mutation disables action buttons for matching row', () => {
    render(
      <PromosTable
        items={[makePromo({ id: 'x', state: 'active' })]}
        onRowClick={vi.fn()}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        pendingId="x"
        emptyLabel="empty"
      />,
    );
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeDisabled();
  });

  test('clicking row fires onRowClick', () => {
    const onRowClick = vi.fn();
    const promo = makePromo({ code: 'CLICKME' });
    render(
      <PromosTable
        items={[promo]}
        onRowClick={onRowClick}
        onActivate={vi.fn()}
        onDeactivate={vi.fn()}
        emptyLabel="empty"
      />,
    );
    fireEvent.click(screen.getByTestId('promo-row-CLICKME'));
    expect(onRowClick).toHaveBeenCalledWith(promo);
  });
});
