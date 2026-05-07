import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BrandMark } from './BrandMark';

describe('BrandMark', () => {
  it('renders the Aura mark asset', () => {
    const { container } = render(<BrandMark alt="Aura Coffee" />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('src')).toBe('/brand/aura-mark.png');
    expect(image?.getAttribute('alt')).toBe('Aura Coffee');
  });

  it('can be decorative when adjacent text already names the brand', () => {
    const { container } = render(<BrandMark decorative />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('alt')).toBe('');
    expect(image?.getAttribute('aria-hidden')).toBe('true');
  });
});
