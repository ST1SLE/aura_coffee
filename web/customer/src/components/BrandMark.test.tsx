import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BrandMark, BrandWordmark } from './BrandMark';

describe('BrandMark', () => {
  it('renders the Aura mark asset', () => {
    const { container } = render(<BrandMark alt="Aura Coffee" />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('src')).toBe('/brand/aura-heart-olive.png');
    expect(image?.getAttribute('alt')).toBe('Aura Coffee');
  });

  it('can render the white mark variant', () => {
    const { container } = render(<BrandMark tone="white" decorative />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('src')).toBe('/brand/aura-heart-white.png');
  });

  it('can be decorative when adjacent text already names the brand', () => {
    const { container } = render(<BrandMark decorative />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('alt')).toBe('');
    expect(image?.getAttribute('aria-hidden')).toBe('true');
  });

  it('renders the Aura wordmark asset', () => {
    const { container } = render(<BrandWordmark alt="Aura Coffee" />);
    const image = container.querySelector('img');

    expect(image?.getAttribute('src')).toBe('/brand/aura-wordmark-olive.png');
    expect(image?.getAttribute('alt')).toBe('Aura Coffee');
  });
});
