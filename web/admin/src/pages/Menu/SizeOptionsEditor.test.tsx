import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import '@/i18n/config';
import { SizeOptionsEditor } from './SizeOptionsEditor';
import * as menuApi from '@/api/menu';

vi.mock('@/api/menu', () => ({
  createSize: vi.fn().mockResolvedValue({ id: 1, menu_item_id: 1, label: 'S', price: 50, available: true }),
  updateSize: vi.fn(),
  deleteSize: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
}));

describe('SizeOptionsEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('SizeOptionsEditor label input is a select of S, M, L', () => {
    render(
      <SizeOptionsEditor
        menuItemId={1}
        sizes={[]}
        onChange={vi.fn()}
        disabled={false}
        onError={vi.fn()}
      />,
    );

    // В строке добавления должен быть select с тремя опциями S, M, L
    const options = screen.getAllByRole('option');
    const labels = options.map((o) => o.textContent);
    expect(labels).toContain('S');
    expect(labels).toContain('M');
    expect(labels).toContain('L');
    expect(options).toHaveLength(3);
  });

  test('SizeOptionsEditor submits price, not price_kopecks', async () => {
    render(
      <SizeOptionsEditor
        menuItemId={1}
        sizes={[]}
        onChange={vi.fn()}
        disabled={false}
        onError={vi.fn()}
      />,
    );

    // Вводим цену
    fireEvent.change(screen.getByPlaceholderText('0.00'), { target: { value: '0.50' } });

    // Нажимаем "Add size"
    fireEvent.click(screen.getByRole('button', { name: /add size/i }));

    await waitFor(() => {
      expect(menuApi.createSize).toHaveBeenCalled();
    });

    const call = vi.mocked(menuApi.createSize).mock.calls[0][0];
    expect(call).toHaveProperty('price');
    expect(call).not.toHaveProperty('price_kopecks');
    expect(call).not.toHaveProperty('volume_ml');
    expect(call.label).toBe('S'); // default первый вариант
    expect(call.price).toBe(50); // 0.50 руб = 50 коп
  });
});
