import { render, screen } from '@testing-library/react';
import { describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { PopularItemsList } from './PopularItemsList';
import type { PopularItem } from '@/api/admin-stats';

const sampleItems: PopularItem[] = [
  { name_ru: 'Латте', name_en: 'Latte', quantity: 28 },
  { name_ru: 'Капучино', name_en: 'Cappuccino', quantity: 17 },
];

describe('PopularItemsList', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
  });

  test('рендерит строки в переданном порядке', () => {
    render(<PopularItemsList items={sampleItems} locale="ru" />);
    const rows = screen.getAllByTestId('popular-items-row');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('Латте');
    expect(rows[0]).toHaveTextContent('28');
    expect(rows[1]).toHaveTextContent('Капучино');
    expect(rows[1]).toHaveTextContent('17');
  });

  test('ru-locale показывает name_ru', () => {
    render(<PopularItemsList items={sampleItems} locale="ru" />);
    expect(screen.getByText('Латте')).toBeInTheDocument();
    expect(screen.queryByText('Latte')).not.toBeInTheDocument();
  });

  test('en-locale показывает name_en', async () => {
    await i18n.changeLanguage('en');
    render(<PopularItemsList items={sampleItems} locale="en" />);
    expect(screen.getByText('Latte')).toBeInTheDocument();
    expect(screen.queryByText('Латте')).not.toBeInTheDocument();
  });

  test('пустой список показывает empty-сообщение', () => {
    render(<PopularItemsList items={[]} locale="ru" />);
    expect(screen.getByTestId('popular-items-empty')).toBeInTheDocument();
    expect(screen.getByTestId('popular-items-empty')).toHaveTextContent('Нет данных за период');
    expect(screen.queryAllByTestId('popular-items-row')).toHaveLength(0);
  });

  test('fallback: если name_en пустой, показываем name_ru даже в en-locale', async () => {
    await i18n.changeLanguage('en');
    render(
      <PopularItemsList
        items={[{ name_ru: 'Только RU', name_en: '', quantity: 5 }]}
        locale="en"
      />,
    );
    expect(screen.getByText('Только RU')).toBeInTheDocument();
  });
});
