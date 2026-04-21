import { render, screen } from '@testing-library/react';
import { describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { UserStatusBadge } from './UserStatusBadge';
import badgeSrc from './UserStatusBadge.tsx?raw';

describe('UserStatusBadge', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  test('renders active with success tone', () => {
    render(<UserStatusBadge status="active" />);
    const el = screen.getByTestId('user-status-active');
    expect(el).toHaveTextContent('Active');
  });

  test('renders blocked with destructive tone', () => {
    render(<UserStatusBadge status="blocked" />);
    const el = screen.getByTestId('user-status-blocked');
    expect(el).toHaveTextContent('Blocked');
    // destructive variant — bg-destructive в классе
    expect(el.className).toContain('bg-destructive');
  });

  test('renders pending_verification with warning tone', () => {
    render(<UserStatusBadge status="pending_verification" />);
    const el = screen.getByTestId('user-status-pending_verification');
    expect(el).toHaveTextContent('Pending verification');
  });

  test('renders deleted with muted tone', () => {
    render(<UserStatusBadge status="deleted" />);
    const el = screen.getByTestId('user-status-deleted');
    expect(el).toHaveTextContent('Deleted');
    expect(el.className).toContain('bg-muted');
  });

  test('source does not import any order-badge module', () => {
    expect(badgeSrc).not.toMatch(/OrderStatus/i);
    expect(badgeSrc).not.toMatch(/order-status/i);
    expect(badgeSrc).not.toMatch(/orders\/.*[Bb]adge/);
  });
});
