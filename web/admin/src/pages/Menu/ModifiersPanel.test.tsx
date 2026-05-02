import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { ModifiersPanel } from './ModifiersPanel';
import * as menuApi from '@/api/menu';

vi.mock('@/api/menu', () => ({
  listModifiers: vi.fn().mockResolvedValue([]),
  createModifier: vi.fn().mockResolvedValue({
    id: 1,
    name_ru: 'Ваниль',
    name_en: 'Vanilla',
    price: 5000,
    available: true,
    sort_order: 0,
  }),
  updateModifier: vi.fn(),
  deleteModifier: vi.fn(),
  setModifierAvailability: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

describe('ModifiersPanel', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.mocked(menuApi.listModifiers).mockResolvedValue([]);
    await i18n.changeLanguage('en');
  });

  test('ModifiersPanel create form has name_ru, name_en, price', async () => {
    render(
      <ModifiersPanel
        modifiers={[]}
        onModifiersChange={vi.fn()}
        currentRole="admin"
        onError={vi.fn()}
      />,
    );

    // Открываем форму добавления
    fireEvent.click(screen.getByRole('button', { name: /new modifier/i }));

    expect(screen.getByLabelText('Name (RU)')).toBeInTheDocument();
    expect(screen.getByLabelText('Name (EN)')).toBeInTheDocument();
    expect(screen.getByLabelText('Price (₽)')).toBeInTheDocument();
  });

  test('ModifiersPanel submits bilingual payload with price', async () => {
    render(
      <ModifiersPanel
        modifiers={[]}
        onModifiersChange={vi.fn()}
        currentRole="admin"
        onError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /new modifier/i }));

    fireEvent.change(screen.getByLabelText('Name (RU)'), {
      target: { value: 'Ваниль' },
    });
    fireEvent.change(screen.getByLabelText('Name (EN)'), {
      target: { value: 'Vanilla' },
    });
    fireEvent.change(screen.getByLabelText('Price (₽)'), {
      target: { value: '50' },
    });

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => {
      expect(menuApi.createModifier).toHaveBeenCalledWith(
        expect.objectContaining({
          name_ru: 'Ваниль',
          name_en: 'Vanilla',
          price: 5000,
        }),
      );
    });

    const call = vi.mocked(menuApi.createModifier).mock.calls[0][0];
    expect(call).not.toHaveProperty('name');
    expect(call).not.toHaveProperty('price_kopecks');
  });

  test('modifier edit/delete icon buttons have modifier-specific accessible names', () => {
    render(
      <ModifiersPanel
        modifiers={[
          {
            id: 1,
            name_ru: 'Ваниль',
            name_en: 'Vanilla',
            price: 5000,
            available: true,
            sort_order: 0,
          },
        ]}
        onModifiersChange={vi.fn()}
        currentRole="admin"
        onError={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('button', { name: 'Edit Vanilla' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Delete Vanilla' }),
    ).toBeInTheDocument();
  });
});
