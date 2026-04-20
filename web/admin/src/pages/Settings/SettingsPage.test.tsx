import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom';
import i18n from '@/i18n/config';
import { SettingsPage } from './SettingsPage';
import { ApiError } from '@/api/client';
import * as api from '@/api/admin-settings';
import { baseResponse } from './testUtils';

describe('SettingsPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    vi.restoreAllMocks();
  });

  it('mount: поля заполнены, Save disabled пока !isDirty', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValue(baseResponse());
    render(<SettingsPage />);

    const latInput = await screen.findByLabelText(/Latitude/i);
    expect((latInput as HTMLInputElement).value).toBe('55.75');
    expect(
      (screen.getByLabelText(/Delivery fee/i) as HTMLInputElement).value,
    ).toBe('150');

    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    expect(saveBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Delivery fee/i), {
      target: { value: '200' },
    });
    expect(saveBtn).toBeEnabled();
  });

  it('422 с loc=[body, working_hours, mon, open] → inline ошибка у понедельника', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValue(baseResponse());
    const err = new ApiError(
      422,
      { detail: [{ loc: ['body', 'working_hours', 'mon', 'open'], msg: 'invalid' }] },
      'HTTP 422',
    );
    vi.spyOn(api, 'updateSettings').mockRejectedValue(err);

    render(<SettingsPage />);

    await screen.findByLabelText(/Latitude/i);

    // Делаем форму dirty, чтобы Save стал активным.
    fireEvent.change(screen.getByLabelText(/Delivery fee/i), {
      target: { value: '200' },
    });

    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() =>
      expect(
        screen.getByTestId('err-working_hours.mon.open'),
      ).toBeInTheDocument(),
    );
  });

  it('happy save: success toast, isDirty сбрасывается (Save снова disabled)', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValue(baseResponse());
    const updated = { ...baseResponse(), delivery_fee: 20000 };
    vi.spyOn(api, 'updateSettings').mockResolvedValue(updated);

    render(<SettingsPage />);

    await screen.findByLabelText(/Latitude/i);

    fireEvent.change(screen.getByLabelText(/Delivery fee/i), {
      target: { value: '200' },
    });

    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    expect(saveBtn).toBeEnabled();

    fireEvent.click(saveBtn);

    await waitFor(() =>
      expect(screen.getByText(/Settings saved/i)).toBeInTheDocument(),
    );

    // После refetch через PUT-ответ initial = form → !isDirty → Save disabled.
    await waitFor(() => expect(saveBtn).toBeDisabled());
    expect(
      (screen.getByLabelText(/Delivery fee/i) as HTMLInputElement).value,
    ).toBe('200');
  });
});
