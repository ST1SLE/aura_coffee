import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import '@/i18n/config';
import { CourierPage } from './CourierPage';

vi.mock('@/pages/Courier/AvailableTab', () => ({
  AvailableTab: () => <div data-testid="available-content">available</div>,
}));

vi.mock('@/pages/Courier/MineTab', () => ({
  MineTab: () => <div data-testid="mine-content">mine</div>,
}));

describe('CourierPage accessibility', () => {
  it('connects tabs to their active tabpanel', () => {
    const { container } = render(<CourierPage />);

    const availableTab = screen.getByRole('tab', { name: /available/i });
    const mineTab = screen.getByRole('tab', { name: /mine/i });
    const panel = screen.getByRole('tabpanel');
    const hiddenMinePanel = container.querySelector('#courier-panel-mine');

    expect(availableTab).toHaveAttribute('id', 'courier-tab-available');
    expect(availableTab).toHaveAttribute(
      'aria-controls',
      'courier-panel-available',
    );
    expect(mineTab).toHaveAttribute('aria-controls', 'courier-panel-mine');
    expect(panel).toHaveAttribute('id', 'courier-panel-available');
    expect(panel).toHaveAttribute('aria-labelledby', 'courier-tab-available');
    expect(hiddenMinePanel).toHaveAttribute('hidden');

    fireEvent.click(mineTab);

    const minePanel = screen.getByRole('tabpanel');
    const hiddenAvailablePanel = container.querySelector(
      '#courier-panel-available',
    );

    expect(minePanel).toHaveAttribute('id', 'courier-panel-mine');
    expect(minePanel).toHaveAttribute('aria-labelledby', 'courier-tab-mine');
    expect(hiddenAvailablePanel).toHaveAttribute('hidden');
    expect(screen.getByTestId('mine-content')).toBeInTheDocument();
  });
});
