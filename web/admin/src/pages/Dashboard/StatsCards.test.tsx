import { render, screen } from '@testing-library/react';
import { describe, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { StatsCards } from './StatsCards';

describe('StatsCards', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
  });

  test('revenue card содержит форматированную сумму с валютой', () => {
    render(<StatsCards revenueKopecks={1234500} ordersCount={42} locale="ru" />);
    const revenueCard = screen.getByTestId('stats-card-revenue');
    expect(revenueCard).toHaveTextContent(/12/);
    expect(revenueCard).toHaveTextContent(/345/);
    expect(revenueCard.textContent).toMatch(/₽|RUB/);
  });

  test('orders card содержит количество', () => {
    render(<StatsCards revenueKopecks={0} ordersCount={42} locale="ru" />);
    const ordersCard = screen.getByTestId('stats-card-orders');
    expect(ordersCard).toHaveTextContent('42');
  });

  test('zero revenue и zero orders отрисовываются', () => {
    render(<StatsCards revenueKopecks={0} ordersCount={0} locale="ru" />);
    const revenueCard = screen.getByTestId('stats-card-revenue');
    const ordersCard = screen.getByTestId('stats-card-orders');
    expect(revenueCard.textContent).toMatch(/0/);
    expect(revenueCard.textContent).toMatch(/₽|RUB/);
    expect(ordersCard).toHaveTextContent('0');
  });

  test('en-locale рендерит английские лейблы и не падает', async () => {
    await i18n.changeLanguage('en');
    render(<StatsCards revenueKopecks={1234500} ordersCount={7} locale="en" />);
    expect(screen.getByTestId('stats-card-revenue')).toHaveTextContent('Revenue');
    expect(screen.getByTestId('stats-card-orders')).toHaveTextContent('Orders');
    expect(screen.getByTestId('stats-card-orders')).toHaveTextContent('7');
  });
});
