import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SectionLoyalty } from './SectionLoyalty';
import { validateLoyalty } from './validation';
import { baseForm } from './testUtils';

describe('SectionLoyalty', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('рендерит loyalty_percent', () => {
    render(<SectionLoyalty form={baseForm()} onChange={() => {}} errors={{}} />);
    expect(screen.getByLabelText(/Points accrual rate/i)).toBeInTheDocument();
  });

  it('boundary: 0 OK, 100 OK, 101 → error', () => {
    expect(validateLoyalty({ ...baseForm(), loyalty_percent: '0' })).toEqual({});
    expect(validateLoyalty({ ...baseForm(), loyalty_percent: '100' })).toEqual({});
    expect(validateLoyalty({ ...baseForm(), loyalty_percent: '101' })).toEqual({
      loyalty_percent: 'out_of_range',
    });
  });

  it('negative → error', () => {
    expect(validateLoyalty({ ...baseForm(), loyalty_percent: '-1' })).toEqual({
      loyalty_percent: 'out_of_range',
    });
  });

  it('non-int строка → error', () => {
    expect(validateLoyalty({ ...baseForm(), loyalty_percent: 'abc' })).toEqual({
      loyalty_percent: 'out_of_range',
    });
  });
});
