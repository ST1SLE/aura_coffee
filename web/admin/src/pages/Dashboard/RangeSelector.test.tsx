import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { RangeSelector } from './RangeSelector';

describe('RangeSelector', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });

  test('рендерит три кнопки c правильными тестовыми id', () => {
    const onChange = vi.fn();
    render(<RangeSelector value="month" onChange={onChange} />);
    expect(screen.getByTestId('range-tab-today')).toBeInTheDocument();
    expect(screen.getByTestId('range-tab-week')).toBeInTheDocument();
    expect(screen.getByTestId('range-tab-month')).toBeInTheDocument();
  });

  test('активная кнопка соответствует value через aria-selected', () => {
    const onChange = vi.fn();
    render(<RangeSelector value="month" onChange={onChange} />);
    expect(screen.getByTestId('range-tab-month')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('range-tab-today')).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByTestId('range-tab-week')).toHaveAttribute('aria-selected', 'false');
  });

  test('клик на today вызывает onChange("today") один раз', () => {
    const onChange = vi.fn();
    render(<RangeSelector value="month" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('range-tab-today'));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('today');
  });

  test('клик на уже-выбранную кнопку всё равно вызывает onChange', () => {
    const onChange = vi.fn();
    render(<RangeSelector value="today" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('range-tab-today'));
    expect(onChange).toHaveBeenCalledWith('today');
  });

  test('ru-locale рендерит русские лейблы', async () => {
    await i18n.changeLanguage('ru');
    const onChange = vi.fn();
    render(<RangeSelector value="month" onChange={onChange} />);
    expect(screen.getByTestId('range-tab-today')).toHaveTextContent('Сегодня');
    expect(screen.getByTestId('range-tab-week')).toHaveTextContent('Неделя');
    expect(screen.getByTestId('range-tab-month')).toHaveTextContent('Месяц');
  });
});
