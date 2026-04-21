import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { UsersTable } from './UsersTable';
import type { UserSummary } from '@/api/admin-users';

function makeUser(overrides: Partial<UserSummary> = {}): UserSummary {
  return {
    id: overrides.id ?? 'u-1',
    display_name: overrides.display_name ?? 'Иван',
    status: overrides.status ?? 'active',
    loyalty_balance: overrides.loyalty_balance ?? 0,
    created_at: overrides.created_at ?? '2026-04-01T10:00:00Z',
    ...overrides,
  };
}

describe('UsersTable', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  test('renders one row per item', () => {
    render(
      <UsersTable
        items={[
          makeUser({ id: '1', display_name: 'Alice' }),
          makeUser({ id: '2', display_name: 'Bob' }),
        ]}
        onSelect={vi.fn()}
        emptyLabel="empty"
      />,
    );
    expect(screen.getByTestId('user-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('user-row-2')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  test('clicking Details invokes onSelect with user id', () => {
    const onSelect = vi.fn();
    render(
      <UsersTable
        items={[makeUser({ id: 'u-42' })]}
        onSelect={onSelect}
        emptyLabel="empty"
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    expect(onSelect).toHaveBeenCalledWith('u-42');
  });

  test('formats loyalty balance with locale thousand separator + pts unit', async () => {
    await i18n.changeLanguage('ru');
    render(
      <UsersTable
        items={[makeUser({ id: 'u-7', loyalty_balance: 1234 })]}
        onSelect={vi.fn()}
        emptyLabel="empty"
      />,
    );
    const cell = screen.getByTestId('user-balance-u-7');
    // ru-RU использует non-breaking space (U+00A0) как thousands sep
    expect(cell.textContent?.replace(/\u00a0/g, ' ')).toBe('1 234 балл.');
  });

  test('empty items renders empty-state', () => {
    render(
      <UsersTable items={[]} onSelect={vi.fn()} emptyLabel="nothing here" />,
    );
    expect(screen.getByTestId('users-empty')).toHaveTextContent('nothing here');
    expect(screen.queryByRole('row')).not.toBeInTheDocument();
  });

  test('DOM contains no phone or phone_hash substring', () => {
    const { container } = render(
      <UsersTable
        items={[makeUser({ id: 'u-1', display_name: 'Иван' })]}
        onSelect={vi.fn()}
        emptyLabel="empty"
      />,
    );
    const html = container.innerHTML.toLowerCase();
    expect(html).not.toContain('phone');
  });

  test('clicking row fires onSelect', () => {
    const onSelect = vi.fn();
    render(
      <UsersTable
        items={[makeUser({ id: 'u-99' })]}
        onSelect={onSelect}
        emptyLabel="empty"
      />,
    );
    fireEvent.click(screen.getByTestId('user-row-u-99'));
    expect(onSelect).toHaveBeenCalledWith('u-99');
  });
});
