import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import '@/i18n/config';
import { CategoryList } from './CategoryList';

vi.mock('@/api/menu', () => ({
  listCategories: vi.fn().mockResolvedValue([]),
  createCategory: vi.fn().mockResolvedValue({
    id: 1,
    type: 'drink',
    name_ru: 'Кофе',
    name_en: 'Coffee',
    sort_order: 0,
    is_visible: true,
  }),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

const defaultProps = {
  selectedId: null,
  onSelect: vi.fn(),
  onCategoriesLoaded: vi.fn(),
  currentRole: 'admin' as const,
  onError: vi.fn(),
};

describe('CategoryList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('CategoryList create form has name_ru, name_en, and type inputs', async () => {
    render(<CategoryList {...defaultProps} />);

    // Форма создания рендерится сразу для admin-роли
    expect(screen.getByLabelText('Name (RU)')).toBeInTheDocument();
    expect(screen.getByLabelText('Name (EN)')).toBeInTheDocument();
    expect(screen.getByLabelText('Type')).toBeInTheDocument();
  });

  test('CategoryList create form POSTs bilingual payload', async () => {
    const { createCategory } = await import('@/api/menu');

    render(<CategoryList {...defaultProps} />);

    fireEvent.change(screen.getByLabelText('Name (RU)'), { target: { value: 'Кофе' } });
    fireEvent.change(screen.getByLabelText('Name (EN)'), { target: { value: 'Coffee' } });
    // Тип уже 'drink' по умолчанию

    fireEvent.click(screen.getByRole('button', { name: /new category/i }));

    await waitFor(() => {
      expect(createCategory).toHaveBeenCalledWith({
        type: 'drink',
        name_ru: 'Кофе',
        name_en: 'Coffee',
        sort_order: 0,
        is_visible: true,
      });
    });
  });
});
