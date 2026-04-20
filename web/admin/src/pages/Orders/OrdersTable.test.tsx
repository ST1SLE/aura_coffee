import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { OrdersTable } from './OrdersTable';
import type { OrderResponse } from '@/api/admin-orders';

function makeOrder(overrides: Partial<OrderResponse> = {}): OrderResponse {
  return {
    id: overrides.id ?? 'uuid-A',
    user_id: overrides.user_id ?? 'user-1',
    status: overrides.status ?? 'paid',
    type: overrides.type ?? 'pickup',
    subtotal: overrides.subtotal ?? 30000,
    discount_amount: overrides.discount_amount ?? 0,
    delivery_fee: overrides.delivery_fee ?? 0,
    total: overrides.total ?? 30000,
    created_at: overrides.created_at ?? '2026-04-20T10:00:00Z',
    items: overrides.items ?? [],
  };
}

describe('OrdersTable', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
  });

  test('renders rows with data-testid', () => {
    render(
      <OrdersTable
        rows={[makeOrder({ id: 'uuid-A' }), makeOrder({ id: 'uuid-B' })]}
        onSelect={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByTestId('order-row-uuid-A')).toBeInTheDocument();
    expect(screen.getByTestId('order-row-uuid-B')).toBeInTheDocument();
  });

  test('clicking Details invokes onSelect with the id', () => {
    const onSelect = vi.fn();
    render(
      <OrdersTable
        rows={[makeOrder({ id: 'uuid-A' })]}
        onSelect={onSelect}
        emptyLabel="empty"
      />,
    );
    fireEvent.click(screen.getByTestId('order-details-uuid-A'));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('uuid-A');
  });

  test('empty rows render emptyLabel and no row testids', () => {
    render(<OrdersTable rows={[]} onSelect={vi.fn()} emptyLabel="Нет заказов" />);
    expect(screen.getByText('Нет заказов')).toBeInTheDocument();
    expect(screen.queryByTestId(/^order-row-/)).not.toBeInTheDocument();
  });
});
