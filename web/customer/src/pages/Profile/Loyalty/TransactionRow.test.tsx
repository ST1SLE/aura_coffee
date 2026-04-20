import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '@/i18n/config';
import '@testing-library/jest-dom/vitest';

import { TransactionRow } from './TransactionRow';
import type { LoyaltyTransaction } from '@/api/loyalty';

const tx = (over: Partial<LoyaltyTransaction> = {}): LoyaltyTransaction => ({
  id: '11111111-1111-1111-1111-111111111111',
  order_id: '22222222-2222-2222-2222-222222222222',
  type: 'accrual',
  amount: 50,
  balance_after: 240,
  description: null,
  created_at: '2026-04-20T12:00:00Z',
  ...over,
});

function renderRow(t: LoyaltyTransaction) {
  return render(
    <MemoryRouter>
      <ul>
        <TransactionRow tx={t} />
      </ul>
    </MemoryRouter>,
  );
}

describe('TransactionRow amount color', () => {
  it('renders positive amount with green class and + sign', () => {
    renderRow(tx({ amount: 50 }));
    const el = screen.getByText('+50');
    expect(el.className).toContain('text-green-600');
  });

  it('renders negative amount with red class', () => {
    renderRow(tx({ amount: -20, type: 'redemption' }));
    const el = screen.getByText('-20');
    expect(el.className).toContain('text-red-600');
  });

  it('renders zero amount in default (no green/red) color', () => {
    renderRow(tx({ amount: 0 }));
    const el = screen.getByText('0');
    expect(el.className).not.toContain('text-green-600');
    expect(el.className).not.toContain('text-red-600');
  });
});

describe('TransactionRow order link', () => {
  it('renders no link when order_id is null', () => {
    renderRow(tx({ order_id: null, type: 'admin_adjustment', description: 'bonus' }));
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('renders link with short id (8 chars) and href /orders/{full_uuid}', () => {
    const uuid = 'abcdef12-3456-7890-abcd-ef1234567890';
    renderRow(tx({ order_id: uuid }));
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', `/orders/${uuid}`);
    expect(link.textContent).toContain('abcdef12');
    expect(link.textContent).not.toContain('3456');
  });
});

describe('TransactionRow type label (i18n)', () => {
  it('uses localized label for accrual', async () => {
    await i18n.changeLanguage('en');
    renderRow(tx({ type: 'accrual' }));
    expect(screen.getByText('Accrual')).toBeInTheDocument();
  });

  it('uses localized label for admin_adjustment', async () => {
    await i18n.changeLanguage('en');
    renderRow(tx({ type: 'admin_adjustment', order_id: null }));
    expect(screen.getByText('Adjustment')).toBeInTheDocument();
  });
});
