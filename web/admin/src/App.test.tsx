import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import '@/i18n/config';
import { App } from '@/App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getAllByText(/Aura Coffee/).length).toBeGreaterThan(0);
  });
});
