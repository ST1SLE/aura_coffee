import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom/vitest';
import i18n from '@/i18n/config';

vi.mock('@/api/notifications', async () => {
  const actual =
    await vi.importActual<typeof import('@/api/notifications')>(
      '@/api/notifications',
    );
  return {
    ...actual,
    listNotifications: vi.fn(),
  };
});

import { listNotifications } from '@/api/notifications';
import { NotificationsPage } from './NotificationsPage';

function notification(over = {}) {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    order_id: '22222222-2222-2222-2222-222222222222',
    channel: 'in_app',
    type: 'order_status_change',
    status: 'sent',
    message_ru: 'Заказ готов',
    message_en: 'Order ready',
    sent_at: '2026-05-02T12:00:00Z',
    created_at: '2026-05-02T12:00:00Z',
    ...over,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/profile/notifications']}>
      <Routes>
        <Route
          path="/profile/notifications"
          element={<NotificationsPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage('en');
});

describe('NotificationsPage', () => {
  it('renders notification text and order link', async () => {
    (listNotifications as Mock).mockResolvedValue({
      notifications: [notification()],
      total_count: 1,
      page: 1,
      per_page: 20,
    });

    renderPage();

    expect(await screen.findByText('Order ready')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Order #22222222/i })).toHaveAttribute(
      'href',
      '/orders/22222222-2222-2222-2222-222222222222',
    );
    expect(listNotifications).toHaveBeenCalledWith(1, 20);
  });

  it('uses localized RU message text', async () => {
    await i18n.changeLanguage('ru');
    (listNotifications as Mock).mockResolvedValue({
      notifications: [notification()],
      total_count: 1,
      page: 1,
      per_page: 20,
    });

    renderPage();

    expect(await screen.findByText('Заказ готов')).toBeInTheDocument();
  });

  it('renders empty state', async () => {
    (listNotifications as Mock).mockResolvedValue({
      notifications: [],
      total_count: 0,
      page: 1,
      per_page: 20,
    });

    renderPage();

    expect(await screen.findByText('No updates yet')).toBeInTheDocument();
  });

  it('loads another page when more rows exist', async () => {
    (listNotifications as Mock)
      .mockResolvedValueOnce({
        notifications: [notification({ id: 'n1', message_en: 'First' })],
        total_count: 2,
        page: 1,
        per_page: 20,
      })
      .mockResolvedValueOnce({
        notifications: [
          notification({ id: 'n2', message_en: 'Second', order_id: null }),
        ],
        total_count: 2,
        page: 2,
        per_page: 20,
      });

    renderPage();

    expect(await screen.findByText('First')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    await waitFor(() => expect(listNotifications).toHaveBeenCalledWith(2, 20));
    expect(await screen.findByText('Second')).toBeInTheDocument();
  });

  it('renders an error state', async () => {
    (listNotifications as Mock).mockRejectedValue(new Error('boom'));

    renderPage();

    expect(
      await screen.findByText('Failed to load notifications'),
    ).toBeInTheDocument();
  });
});
