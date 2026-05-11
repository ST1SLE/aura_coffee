import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionOperations } from './SectionOperations';
import { baseForm } from './testUtils';

describe('SectionOperations', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('renders ordering pause switch and emits boolean changes', () => {
    const onOrderingPausedChange = vi.fn();
    render(
      <SectionOperations
        form={baseForm()}
        onOrderingPausedChange={onOrderingPausedChange}
        errors={{}}
      />,
    );

    const toggle = screen.getByRole('switch', {
      name: /pause order placement/i,
    });
    expect(toggle).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(toggle);
    expect(onOrderingPausedChange).toHaveBeenCalledWith(true);
  });
});
