import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { render, fireEvent, act, screen } from '@testing-library/react';
import '@/i18n/config';

vi.mock('@/api/yandex_maps', async () => {
  const actual = await vi.importActual<typeof import('@/api/yandex_maps')>(
    '@/api/yandex_maps',
  );
  return {
    ...actual,
    suggest: vi.fn(),
  };
});

import { suggest, MapsUnavailableError } from '@/api/yandex_maps';
import { AddressAutocomplete, type AddressValue } from './AddressAutocomplete';

function setup(initial: AddressValue = { text: '', lat: null, lon: null }) {
  const onChange = vi.fn();
  const utils = render(
    <AddressAutocomplete value={initial} onChange={onChange} lang="ru_RU" />,
  );
  return { onChange, ...utils };
}

async function flushPromises() {
  // Let pending then/catch callbacks from suggest() settle.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('AddressAutocomplete debounce', () => {
  it('fires suggest after 300ms with text and lang', async () => {
    (suggest as Mock).mockResolvedValue([]);
    const { container } = setup();

    const input = container.querySelector('input')!;
    fireEvent.change(input, { target: { value: 'Нев' } });

    expect(suggest).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(suggest).toHaveBeenCalledOnce();
    expect(suggest).toHaveBeenCalledWith('Нев', 'ru_RU');
  });

  it('rapid typing cancels prior debounce — single call', async () => {
    (suggest as Mock).mockResolvedValue([]);
    const { container } = setup();
    const input = container.querySelector('input')!;

    fireEvent.change(input, { target: { value: 'Нев' } });
    await act(async () => {
      vi.advanceTimersByTime(100);
    });
    fireEvent.change(input, { target: { value: 'Невский' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(suggest).toHaveBeenCalledOnce();
    expect(suggest).toHaveBeenCalledWith('Невский', 'ru_RU');
  });

  it('does NOT call suggest for query < 3 chars', async () => {
    (suggest as Mock).mockResolvedValue([]);
    const { container } = setup();
    const input = container.querySelector('input')!;

    fireEvent.change(input, { target: { value: 'Не' } });
    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(suggest).not.toHaveBeenCalled();
  });

  it('ignores stale response via requestId guard', async () => {
    let resolveA!: (v: unknown) => void;
    let resolveB!: (v: unknown) => void;
    const promiseA = new Promise((r) => (resolveA = r));
    const promiseB = new Promise((r) => (resolveB = r));
    (suggest as Mock)
      .mockImplementationOnce(() => promiseA)
      .mockImplementationOnce(() => promiseB);

    const { container } = setup();
    const input = container.querySelector('input')!;

    fireEvent.change(input, { target: { value: 'Нев' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    fireEvent.change(input, { target: { value: 'Невский' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    // B resolves first with fresh results
    const freshItems = [{ text: 'Невский пр., 10', lat: 1, lon: 2 }];
    resolveB(freshItems);
    await flushPromises();

    // A resolves later with stale results — must be ignored
    resolveA([{ text: 'STALE', lat: 0, lon: 0 }]);
    await flushPromises();

    // Dropdown should contain fresh item, not stale
    expect(screen.queryByText('STALE')).toBeNull();
    expect(screen.queryByText('Невский пр., 10')).not.toBeNull();
  });
});

describe('AddressAutocomplete selection', () => {
  it('calls onChange with {text, lat, lon} and closes dropdown', async () => {
    const items = [
      { text: 'Невский пр., 1', lat: 59.93, lon: 30.36 },
      { text: 'Невский пр., 2', lat: 59.93, lon: 30.37 },
    ];
    (suggest as Mock).mockResolvedValue(items);

    const { container, onChange } = setup();
    const input = container.querySelector('input')!;
    fireEvent.change(input, { target: { value: 'Нев' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    await flushPromises();

    const option = screen.getByText('Невский пр., 2');
    fireEvent.mouseDown(option);

    expect(onChange).toHaveBeenCalledWith({
      text: 'Невский пр., 2',
      lat: 59.93,
      lon: 30.37,
    });
    // Dropdown closed
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});

describe('AddressAutocomplete degraded mode', () => {
  it('switches to degraded on 503 / MapsUnavailableError', async () => {
    (suggest as Mock).mockRejectedValue(new MapsUnavailableError());
    const { container } = setup();

    const input = container.querySelector('input')!;
    fireEvent.change(input, { target: { value: 'Нев' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    await flushPromises();

    expect(screen.queryByRole('listbox')).toBeNull();
    expect(screen.queryByRole('status')).not.toBeNull();
  });

  it('stops further suggest calls once degraded', async () => {
    (suggest as Mock).mockRejectedValue(new MapsUnavailableError());
    const { container } = setup();
    const input = container.querySelector('input')!;

    fireEvent.change(input, { target: { value: 'Нев' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    await flushPromises();

    expect(suggest).toHaveBeenCalledOnce();

    fireEvent.change(input, { target: { value: 'Невский' } });
    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    // Still only one call — degraded blocks further requests
    expect(suggest).toHaveBeenCalledOnce();
  });

  it('blur in degraded emits onChange with lat/lon null', async () => {
    (suggest as Mock).mockRejectedValue(new MapsUnavailableError());
    const { container, onChange } = setup();
    const input = container.querySelector('input')!;

    fireEvent.change(input, { target: { value: 'Улица' } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    await flushPromises();

    fireEvent.change(input, { target: { value: 'Улица Ленина 1' } });
    fireEvent.blur(input);

    // Последний вызов onChange (после blur) — с актуальным текстом и null-координатами
    const calls = onChange.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    const last = calls[calls.length - 1][0];
    expect(last).toEqual({ text: 'Улица Ленина 1', lat: null, lon: null });
  });
});
